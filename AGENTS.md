# Repository guidance

These instructions apply to coding agents working in this repository, including GitHub Copilot and Google Antigravity.

## Command execution and approval

- Do not execute commands, scripts, tests, builds, linters, package managers, application servers, containers, or generated code.
- Do not use tools to run code or change machine-wide settings.
- When a command would help, explain what it does, why it is needed, and its exact command line. Wait for the user to run it or explicitly approve that specific execution before proceeding.
- Do not treat a general request to implement a feature as approval to run commands.
- Reading source and documentation is allowed. Make focused source changes when the user has requested implementation.
- Never commit, push, install dependencies, or change machine-wide settings unless the user explicitly requests and approves that specific action.

## Safety and design

- Treat model output, user input, stored state, and external data as untrusted.
- Never execute, evaluate, or dynamically interpret model-generated content. Do not add `eval`, `exec`, shell dispatch, generated JavaScript, or model-defined tools.
- Keep browser behavior server-driven. Actions must resolve through an application-owned allowlist and have validated, bounded inputs.
- Keep model providers and network access disabled unless explicitly configured for a feature. The application should bind to loopback by default.
- Use narrow capabilities, explicit validation, safe error handling, and maintained dependencies. Do not claim that the system is invulnerable or that prompt injection can be eliminated.
- Do not expose secrets in source, prompts, logs, tests, or responses. Use placeholders for example configuration.

## Engineering practice

- Read the relevant code, tests, and [`docs/architecture.md`](docs/architecture.md) before proposing changes.
- Keep changes focused, preserve existing behavior, and update directly related documentation.
- Add or update tests for changed behavior, but do not run them without the user's specific approval.
- Explain security trade-offs and list any commands that still need to be run by the user.
- Keep shared project configuration in version control; do not add personal editor state or local credentials.
