"""Run the PR1 tests offline, optionally against an unmodified source checkout.

Only the test process is started. Application startup and external services are
not used; credentials are removed and network/provider/order calls are guarded.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


REPO = Path(__file__).resolve().parents[2]
UNIT = REPO / 'tests/unit/app'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=REPO,
                    help='Product checkout; shared tests always come from this runner checkout')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--suite', choices=('regression', 'comparison'), default='regression')
parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
args = parser.parse_args()
source, output = args.source.resolve(), args.output.resolve()
if not (source / 'core/workflow/engine.py').is_file():
    parser.error('--source must be a complete product checkout')
output.mkdir(parents=True, exist_ok=True)

if not args.child:
    keep = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP', 'PATH',
            'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA',
            'PROGRAMDATA', 'PROGRAMFILES', 'OS'}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    env.update(PR1_SOURCE_ROOT=str(source), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               DOTENV_FILE=str(output / 'offline.env'))
    (output / 'offline.env').write_text('# No credentials or services.\n', encoding='utf-8')
    with (output / 'tests.txt').open('w', encoding='utf-8') as stream:
        run = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
            '--source', str(source), '--output', str(output), '--suite', args.suite, '--child'],
            env=env, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    print(json.dumps({'suite': args.suite, 'source': str(source),
                      'exit_code': run.returncode, 'output': str(output)}))
    raise SystemExit(run.returncode)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path[:0] = [str(source), str(UNIT)]
os.chdir(source)
record = {'suite': args.suite, 'source': str(source), 'cases': [],
          'blocked_transport': [], 'real_model_order_attempts': [],
          'blocked_local_probes': [],
          'wrong_source_calls': [], 'executed_product_files': {},
          'installed': {d.metadata['Name']: d.version for d in metadata.distributions()}}


class ForbiddenOperation(BaseException):
    pass


def audit(event, values):
    if event in {'socket.connect', 'socket.bind'}:
        caller = sys._getframe(1)
        if (event == 'socket.bind' and values[1] == ('::1', 0)
                and caller.f_code.co_name == '_has_ipv6'
                and caller.f_code.co_filename.replace('\\', '/').endswith('/urllib3/util/connection.py')):
            # Refuse urllib3's import-time capability probe with the OSError it
            # expects. This creates no listening socket or service connection.
            record['blocked_local_probes'].append('urllib3 IPv6 bind probe')
            raise OSError('Offline runner disables the local IPv6 probe')
        # Windows implements stdlib asyncio wakeups with a loopback socketpair.
        frame = sys._getframe(1)
        while frame:
            if (frame.f_code.co_name in {'socketpair', '_fallback_socketpair'}
                    and Path(frame.f_code.co_filename).name == 'socket.py'):
                return
            frame = frame.f_back
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'socket.sendto',
                 'socket.sendmsg', 'subprocess.Popen', 'os.system'}:
        record['blocked_transport'].append(event)
        raise ForbiddenOperation('Offline tests forbid network/process startup')
    if event == 'open' and values and isinstance(values[0], (str, bytes)):
        name = Path(os.fsdecode(values[0])).name
        if name == '.env' or name.startswith('.env.'):
            record['blocked_transport'].append('production dotenv')
            raise ForbiddenOperation('Offline tests forbid production dotenv')


def profile(frame, event, value):
    if event != 'call':
        return
    filename = frame.f_code.co_filename.replace('\\', '/').lower()
    name = frame.f_code.co_name
    # Record the complete product bodies loaded by the AST test boundaries.
    for candidate in (source, REPO):
        prefix = str(candidate).replace('\\', '/').lower() + '/'
        if filename.startswith(prefix):
            relative = filename[len(prefix):]
            if relative.startswith(('app/', 'core/', 'tradingagents/')):
                if candidate != source:
                    record['wrong_source_calls'].append(filename)
                    raise ForbiddenOperation('Product code came from the other checkout')
                record['executed_product_files'][frame.f_code.co_filename] = True
            break
    provider = any(part in filename for part in (
        '/openai/resources/', '/langchain_core/language_models/', '/langchain_openai/',
        '/core/llm/', '/tradingagents/llm_adapters/', '/dashscope/'))
    if ((provider and name in {'create', 'invoke', 'ainvoke', 'generate', 'agenerate',
                              'stream', 'astream', '__call__', 'generate_content'})
            or name in {'place_order', 'submit_order', 'execute_order', 'execute_trade',
                        'order_stock', 'buy_stock', 'sell_stock'}):
        record['real_model_order_attempts'].append({'file': filename, 'name': name})
        raise ForbiddenOperation('Real model/order calls are forbidden')


sys.addaudithook(audit)
sys.setprofile(profile)
threading.setprofile(profile)
import pytest


class Results:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.when == 'call' or report.failed:
            case = dict(getattr(item, 'comparison_evidence', {}))
            case.update(nodeid=item.nodeid, phase=report.when, outcome=report.outcome,
                        control=bool(item.get_closest_marker('control')))
            if call.excinfo:
                case.update(exception_type=call.excinfo.type.__name__,
                            message=str(call.excinfo.value), traceback=str(report.longrepr))
            record['cases'].append(case)


names = ['test_pr1_comparison'] if args.suite == 'comparison' else [
    'test_c1_degraded_nodes', 'test_c2_market_quality', 'test_c2_langgraph_integration',
    'test_review_regressions', 'test_pr1_task_entry']
code = 3
try:
    code = pytest.main(['-p', 'no:cacheprovider', '--confcutdir=' + str(UNIT), '-o', 'addopts=',
        '-o', 'markers=reproduction: upstream business failure\ncontrol: normal path on both checkouts',
        *[str(UNIT / (name + '.py')) for name in names], '-q', '--tb=short',
        '--junitxml=' + str(output / 'tests.xml')], plugins=[Results()])
finally:
    sys.setprofile(None)
    threading.setprofile(None)
    record.update(pytest_exit_code=int(code),
        test_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(UNIT.glob('test_*.py'))
                     if path.stem in names or path.stem in {
                         'test_c1_degraded_nodes', 'test_c2_market_quality',
                         'test_c2_langgraph_integration', 'test_pr1_task_entry'}},
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    record['executed_product_files'] = {
        path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in record['executed_product_files']}
    (output / 'results.json').write_text(json.dumps(record, ensure_ascii=False,
        indent=2, default=str) + '\n', encoding='utf-8')
if (record['blocked_transport'] or record['real_model_order_attempts']
        or record['wrong_source_calls']):
    raise SystemExit('Offline boundary violation; see results.json')
raise SystemExit(code)
