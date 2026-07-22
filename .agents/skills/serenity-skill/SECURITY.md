# Security policy

This skill is designed to be safe to audit and easy to run locally.

## Security design

- Bundled scripts use Python standard library only.
- Bundled scripts run locally with Python standard library inputs.
- Bundled scripts have no broker, wallet, trade-execution, or secret-reading functionality.
- The skill instructs agents to use public sources and user-approved tools.
- The skill treats third-party social posts as leads and asks for stronger sources before high-confidence claims.

## Reporting issues

Open an issue with:

1. File path.
2. Risk description.
3. Reproduction steps.
4. Suggested fix.

## Threat model

Agent Skills can contain executable code and instructions. Users should review all files before installing any third-party skill, especially skills that request shell access, credentials, wallet access, browser access, or brokerage access.
