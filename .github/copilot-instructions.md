# GitHub Copilot instructions

Follow the repository-wide rules in [`AGENTS.md`](../AGENTS.md) for all work. In particular, do not run commands, tests, builds, package managers, servers, containers, or generated code. Explain a proposed command and wait for explicit approval of that specific execution.

Use [`docs/architecture.md`](../docs/architecture.md) as the current design proposal, not as proof that a security property has been implemented. Treat model output and user input as untrusted; keep actions server-side, pre-registered, and narrowly authorized.
