# C1 / C2 offline verification

These tests exercise the actual market analyst, lexical quality validator,
workflow compilation and node wrappers, task service, result persistence, and
FastAPI result serialization. LangGraph scheduling and reducers are real.
Models, tools, configuration/authentication, and storage are local fakes.
Application startup and provider-registering constructors are not exercised.

The loaders execute complete product function/method AST bodies unchanged.
The same tests can select a separate complete source checkout, so upstream
reproductions do not fail merely because a newly added helper is absent.
The runner cuts off parent conftest files to keep their sys.path changes from
mixing the two source checkouts.

Use an existing test environment containing Python 3.12, pytest, FastAPI/httpx,
LangGraph 0.4.8, langchain-core 0.3.65, and their dependencies. The recorded run
uses Python 3.12.14 and pytest 9.1.1. No installation or lock change is performed
by the runner, and no API keys or service addresses are required.

From this checkout, with `python` pointing to that environment:

```text
python -I -B tests/offline/run_pr1.py --output /absolute/new-output/regression
python -I -B tests/offline/run_pr1.py --suite comparison --output /absolute/new-output/patched
python -I -B tests/offline/run_pr1.py --suite comparison --source /absolute/upstream-checkout --output /absolute/new-output/baseline
```

Each command writes `tests.txt`, `tests.xml`, and `results.json` to the specified
output directory. Regression and patched comparison should exit zero. Against
the original upstream baseline `51060a7682cf51810b4bc3a704829438d18cd8dc`, comparison
should exit one: 26 call-phase `BusinessMismatch` failures and 7 passing normal
controls. Collection/setup failures, missing interfaces, and guard violations
are invalid reproductions. Shared test/runner hashes and installed versions
must agree between the two comparison results.

Regression covers 95 cases: the 83 C1/C2/state-merge regressions plus 12 task
entry cases. Comparison covers 33 cases, including the task-service-to-Web
chain with both state schemas, normal/warning/critical reports, the existing
report-generation fallback, and a wrapped peer failure. Sync and async engine
streaming are both covered. Fake generation/tool call counts prove this change
does not add quality retries.

The child process removes inherited credentials, disables tracing and automatic
pytest plugin loading, and rejects external network/DNS/process and real
model/order calls. The stdlib asyncio wakeup socketpair is permitted; urllib3's
local IPv6 capability probe is refused and recorded separately. No Redis,
MongoDB, worker process, recovery, or resume service is started.

GitHub Actions runs the same suites for pull requests targeting `v3.0`, including
Drafts. The single Windows job checks out the exact PR head and the original
baseline separately, creates a new Python 3.12.14 environment with pinned uv
0.12.7 and the 38 distributions in `requirements-pr1.txt`, without installing
the full application. `uv.lock` is not used or changed by this test job.
Dependency preparation and artifact upload use the network; the test processes
keep the existing offline guards and use no secrets or real services.

`verify_pr1_results.py` requires runner exit codes `0/1/0` for regression,
upstream comparison, and PR1 comparison respectively. It checks JUnit and JSON
counts and identities, exact dependency versions and shared test bytes/inputs,
the original BusinessMismatch failures, 60 normal Web field equalities, and the
zero-attempt guards. Any collection/setup/teardown error, skip, unexpected
failure, source mismatch, or boundary violation fails the job. The three run
logs, JUnit files, JSON evidence, and summary are always uploaded as artifacts.

For local verification, write the three actual runner exit codes to
`process-exit-codes.json` in the output root, then run:

```text
python -I -B tests/offline/verify_pr1_results.py --results /absolute/output-root --candidate /absolute/this-checkout --baseline /absolute/upstream-checkout --head-sha FULL_CANDIDATE_SHA
```

The workflow uses read-only repository contents permission. A maintainer may
need to approve an external contributor's workflow run under the upstream's
Actions policy; the PR can remain a Draft throughout validation.
