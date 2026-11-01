"""Same fake inputs and business assertions on upstream and PR1.

Only BusinessMismatch in the call phase counts as an upstream reproduction.
Imports, fixture failures and missing methods never count as a fixed bug.
"""
import asyncio
from copy import deepcopy
import json
import pytest
from test_c1_degraded_nodes import (no_external_connections, service, web, task,
    raw_result, payload, PUBLIC_NODES, request_result)
from test_c2_market_quality import runtime, market, execute, GOOD, WARNING
from test_c2_langgraph_integration import graph_runtime, make_run
from test_pr1_task_entry import task_runtime, run_entry, FakeCollection

class BusinessMismatch(AssertionError):
    pass


@pytest.mark.reproduction
def test_selected_task_result_is_not_overwritten_by_legacy_source(web, evidence):
    selected = payload()
    web.db.unified_analysis_tasks.find_one.return_value = {
        'task_id': task().task_id, 'task_params': task().task_params, 'result': selected}
    legacy = payload(None)
    legacy['reports'] = {'market_report': 'Different legacy snapshot'}
    web.db.analysis_tasks.find_one.return_value = {'result': legacy}
    response = request_result(web)
    evidence({'selected': selected, 'legacy': legacy}, response, {
        'selected task source retained': response.get('source') == 'unified_tasks',
        'selected report retained': response.get('reports') == selected['reports'],
        'selected degradation retained': response.get('degraded_nodes') == PUBLIC_NODES,
    })


@pytest.fixture
def evidence(request):
    record = {'scenario': request.node.nodeid, 'inputs': {}, 'observed': {}, 'checks': {}}
    request.node.comparison_evidence = record
    def verify(inputs, observed, checks):
        record.update(inputs=inputs, observed=observed, checks=checks)
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise BusinessMismatch('BUSINESS: ' + '; '.join(failed))
    return verify


@pytest.mark.parametrize('source', ['memory', 'task', 'report'])
@pytest.mark.parametrize('degraded', [pytest.param(True, marks=pytest.mark.reproduction),
                                     pytest.param(False, marks=pytest.mark.control)])
def test_c1_formatter_persistence_web(service, web, source, degraded, evidence):
    raw = raw_result()
    if not degraded:
        raw.pop('degraded_nodes')
    before = deepcopy(raw)
    item = task()
    item.result = service._format_analysis_result(raw, item)
    item.result['stock_name'] = '离线示例'
    asyncio.run(service._update_task(item))
    saved_task = deepcopy(service.collection.update_one.call_args.args[1]['$set'])
    saved_task.update(status='completed', task_params=item.task_params)
    saved = asyncio.run(service._save_to_analysis_reports(item, item.result))
    assert saved, 'Infrastructure: fake report storage failed'
    report = deepcopy(service.db.analysis_reports.insert_one.call_args.args[0])
    if source == 'memory':
        web.state.get_task_status.return_value = {'status': 'completed', 'result_data': saved_task['result']}
    elif source == 'task':
        web.db.unified_analysis_tasks.find_one.return_value = saved_task
    else:
        web.db.analysis_reports.find_one.return_value = report
    response = request_result(web)
    stages = {'formatted': item.result, 'task': saved_task['result'], 'report': report, 'web': response}
    checks = {f'{stage}: degradation identity preserved' if degraded else f'{stage}: no false degradation':
              value.get('degraded_nodes') == PUBLIC_NODES if degraded else not value.get('degraded_nodes')
              for stage, value in stages.items()}
    checks.update({'business report still available': bool(response.get('reports')),
                   'raw input unchanged': raw == before,
                   'private exception not published': 'do-not-publish' not in json.dumps(response)})
    evidence({'raw': raw, 'source': source}, stages, checks)


@pytest.mark.reproduction
@pytest.mark.parametrize('source', ['memory', 'unified_tasks', 'mongodb', 'analysis_tasks'])
def test_c1_web_projection_independently(web, source, evidence):
    value = payload()
    if source == 'memory':
        web.state.get_task_status.return_value = {'status': 'completed', 'result_data': value}
    elif source == 'unified_tasks':
        web.db.unified_analysis_tasks.find_one.return_value = {'task_id': task().task_id, 'status': 'completed',
                                                               'task_params': task().task_params, 'result': value}
    elif source == 'mongodb':
        web.db.analysis_reports.find_one.return_value = value
    else:
        web.db.analysis_tasks.find_one.return_value = {'symbol': '000001', 'result': value}
    response = request_result(web)
    evidence({'source': source, 'result': value}, response, {
        'Web preserves node identity': response.get('degraded_nodes') == PUBLIC_NODES,
        'Web keeps report': response.get('reports') == value['reports'],
        'Web redacts exception context': 'do-not-publish' not in json.dumps(response),
    })


@pytest.mark.reproduction
@pytest.mark.parametrize('incomplete', ['memory', 'task'])
def test_c1_incomplete_source_falls_back_to_report(web, incomplete, evidence):
    shell = {'reports': {}, 'summary': '', 'decision': {},
             'degraded_nodes': {'old_node': {'agent_id': 'old_agent'}}}
    if incomplete == 'memory':
        web.state.get_task_status.return_value = {'status': 'completed', 'result_data': shell}
    else:
        web.db.unified_analysis_tasks.find_one.return_value = {'task_id': task().task_id,
                                                              'status': 'completed', 'result': shell}
    value = payload()
    web.db.analysis_reports.find_one.return_value = value
    response = request_result(web)
    evidence({'incomplete': incomplete, 'shell': shell, 'report': value}, response, {
        'usable report fallback selected': response.get('source') == 'mongodb',
        'report snapshot degradation identity preserved': response.get('degraded_nodes') == PUBLIC_NODES,
        'report content retained': response.get('reports') == value['reports'],
    })


@pytest.mark.parametrize('content,severity', [
    pytest.param(GOOD, None, id='normal', marks=pytest.mark.control),
    pytest.param(WARNING, 'warning', id='warning', marks=pytest.mark.reproduction),
    pytest.param('', 'critical', id='critical', marks=pytest.mark.reproduction),
])
@pytest.mark.parametrize('tools', [True, False], ids=['tools', 'no-tools'])
def test_c2_actual_analyst_checks_without_retry(market, content, severity, tools, evidence):
    output = execute(market, content, tools)
    flags = output.get('quality_flags', [])
    checks = {'original report retained': output.get('market_report') == content,
              'single fake generation': market.invoke_with_tools.call_count + market._invoke_llm_with_trace.call_count == 1,
              'no quality retry': market._check_and_retry_quality.call_count == 0}
    checks['correct quality marking'] = (len(flags) == 1 and flags[0].get('severity') == severity
        and flags[0].get('retried') is False) if severity else not flags
    checks['critical mapped to node degradation'] = bool(output.get('_node_errors')) == (severity == 'critical')
    evidence({'content': content, 'tools': tools}, output, checks)


@pytest.mark.parametrize('schema', ['dynamic', 'fallback'])
@pytest.mark.parametrize('kind', [
    pytest.param('normal', marks=pytest.mark.control),
    pytest.param('warning', marks=pytest.mark.reproduction),
    pytest.param('critical', marks=pytest.mark.reproduction),
    pytest.param('provider-fallback', marks=pytest.mark.reproduction),
    pytest.param('wrapped-error', marks=pytest.mark.reproduction),
])
def test_actual_entry_quality_to_web(task_runtime, schema, kind, evidence):
    rt = task_runtime
    rt.scenario.schema = schema
    rt.scenario.content = {'normal': GOOD, 'warning': WARNING, 'critical': '',
                           'provider-fallback': None, 'wrapped-error': GOOD}[kind]
    rt.scenario.peer_failure = kind == 'wrapped-error'
    result = asyncio.run(run_entry(rt))
    engine_output = rt.engines[0]._current_execution.outputs
    consumed = [state for name, state, _ in rt.node_inputs if name == 'research']
    assert len(consumed) == 1, 'Infrastructure/graph scheduling: expected exactly one consumer'
    expected_nodes = {'entry_market'} if kind in {'critical', 'provider-fallback'} else {'entry_news'} if kind == 'wrapped-error' else set()
    flags = consumed[0].get('quality_flags', [])
    prompts = rt.builders[0].offline.researcher._llm.invoke.call_args.args[0]
    prompt = '\n'.join(message.content for message in prompts)
    responses = {}
    for source in ('memory', 'task', 'report'):
        rt.memory.online = source == 'memory'
        rt.web.db.unified_analysis_tasks = rt.tasks if source != 'report' else FakeCollection('empty', [])
        response = rt.web.client.get(f'/api/analysis/tasks/{result.task_id}/result')
        assert response.status_code == 200, response.text
        responses[source] = response.json()['data']
    severity = {'warning': 'warning', 'critical': 'critical', 'provider-fallback': 'critical'}.get(kind)
    checks = {'task legitimately completed': result.status == 'completed',
        'same flags consumed and retained by engine': engine_output.get('quality_flags', []) == flags,
        'no automatic quality retries': rt.builders[0].offline.market._check_and_retry_quality.call_count == 0,
        'exactly one fake model invocation': rt.builders[0].offline.model.invoke.call_count == 1,
        'exactly one fake tool invocation': rt.builders[0].offline.tool.invoke.call_count == 1,
        'quality reaches consumer': (len(flags) == 1 and flags[0].get('severity') == severity) if severity else not flags,
        'quality changes downstream prompt': ('market_analyst_v2' in prompt and
            ('质量不合格' if severity == 'critical' else '质量存疑') in prompt) if severity else '质量提示' not in prompt,
    }
    for source, data in responses.items():
        checks[source + ': correct degradation nodes'] = set(data.get('degraded_nodes', {})) == expected_nodes
        checks[source + ': report present'] = bool(data.get('reports'))
        checks[source + ': private details redacted'] = 'PRIVATE-' not in json.dumps(data)
    evidence({'schema': schema, 'kind': kind, 'content': rt.scenario.content}, {
        'engine': engine_output, 'consumer': consumed[0], 'prompt': prompt,
        'persisted_task': rt.tasks.documents, 'reports': rt.reports.documents, 'web': responses}, checks)


@pytest.mark.reproduction
@pytest.mark.parametrize('schema', ['dynamic', 'fallback'])
@pytest.mark.parametrize('asynchronous', [False, True], ids=['sync', 'async'])
def test_engine_retains_parallel_merged_flags(graph_runtime, schema, asynchronous, evidence):
    run = make_run(graph_runtime, schema, '', 'critical')
    result = asyncio.run(run.engine.execute_async(run.inputs)) if asynchronous else run.engine.execute(run.inputs)
    assert len(run.seen) == 1, 'Infrastructure/graph scheduling: expected one consumer'
    consumed = run.seen[0]
    observed_flags = result.get('quality_flags', [])
    evidence({'schema': schema, 'async': asynchronous, 'market_report': '', 'peer_severity': 'critical'},
        {'output': result, 'consumer': consumed}, {
        'parallel flags both retained': {flag.get('agent_id') for flag in observed_flags} == {'market_analyst_v2', 'news_analyst_v2'},
        'engine agrees with merged consumer state': observed_flags == consumed.get('quality_flags', []),
        'empty later update does not erase degradation': set(result.get('degraded_nodes', {})) == {'market_node', 'news_node'},
        'earlier market report survives later node updates': result.get('market_report') == '',
    })
