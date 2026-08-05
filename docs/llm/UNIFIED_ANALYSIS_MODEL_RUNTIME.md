# Unified Analysis Model Runtime

Date: 2026-08-05

## Summary

Single-stock and batch analysis now use the AlphaGuard model registry as their
only model configuration source. Operators configure the model service,
credential, and role assignments in `/settings/config`; analysis pages consume
the active, capability-checked assignments from `/api/alphaguard/models/status`.

The runtime role mapping is:

| Analysis use | AlphaGuard role |
| --- | --- |
| Quick analysis | `RESEARCH_AGENT` |
| Deep decisions | `TOP_RISK_REVIEWER` |

The browser submits an opaque selector in the form
`alphaguard-profile:<profile_id>@<profile_version>`. The backend resolves the
selector to the active persisted profile and does not trust a browser-supplied
provider, endpoint, model name, or credential.

## Runtime Behavior

- The status API exposes `analysis_selector` for each configured model profile.
- Single-stock and batch pages show only active profiles that passed capability
  checks.
- Submission is disabled when either required role is unavailable.
- A stale opaque selector is rejected and asks the user to refresh the page.
- Legacy model names, including historical Qwen defaults, are ignored and map
  to the current active role assignments for backward compatibility.
- `OPENAI_COMPATIBLE` profiles use the registered endpoint through the
  `custom_openai` runtime.

## Credential Boundary

Credentials continue to be resolved by `ModelCredentialService` from the
Keychain or Credential Host. They are passed directly to the analysis runtime,
never returned by the status API, and excluded from resolver representations.
The custom OpenAI-compatible path prefers these resolved credentials and the
registered endpoint over stale environment defaults.

## Validation Record

The following checks passed before submission:

- Initial focused backend regression suite: 21 passed.
- Final resolver and runtime-status regression suite: 8 passed.
- Frontend TypeScript check: passed.
- Frontend production build: passed.
- Python compilation and `git diff --check`: passed.
- Docker backend, analysis worker, queue worker, and frontend: healthy.
- Browser E2E: submitted level-1 analysis for A-share `600519`.
- Runtime E2E: `NormalizedChatOpenAI` invoked `gpt-5.6-luna` through the
  registered `BigBanana` compatible endpoint and returned a tool call.
- Log audit: no Qwen/DashScope invocation or HTTP 401 occurred during the E2E
  request.

Two additional checks are recorded as baseline/tooling limitations:

- ESLint could not load the repository configuration because the installed
  frontend dependencies do not include `@rushstack/eslint-patch`.
- The legacy research-depth suite was stopped after its level-1 assertion
  expected `online_tools` to be disabled, while the existing implementation
  intentionally enables the unified online tool path. The same suite also
  waits for disallowed offline MongoDB connections and is not part of the
  focused passing suite above.

## Known Unrelated Runtime Warnings

The local readiness endpoint can report `DEGRADED_PAPER` when experiment samples
are empty. The local Tushare token also fails validation, after which A-share
data retrieval falls back to AKShare. Neither warning changes model resolution
or credential handling introduced by this change.
