# Preliminary architecture concept

This document outlines the current concept. It does not describe an existing implementation or a final architecture. Components and workflows are expected to evolve as the project develops.

```mermaid
flowchart TD
    B[Browser<br/>URL or named action]
    S[Server<br/>Request and session state]
    O[Orchestration<br/>Context and workflow]
    L[Language model<br/>Content or action proposal]
    A[Application actions<br/>Defined in advance]
    H[HTML response<br/>Validation and rendering]

    B --> S
    S --> O
    O <-->|Context and proposal| L
    O -->|Validated selection| A
    A --> O
    O --> H
    H --> B
```

## Core concepts

- Page content is intended to be generated at runtime with language-model assistance.
- Interactions are intended to be submitted to the server as named requests; the model is not to provide executable browser JavaScript.
- Actions and tools are intended to be defined by the application and constrained on the server.
- User input, stored state, and model responses are treated as untrusted.
- Context and session state are intended to be selected and managed separately.
- Model access, external connections, and persistent storage remain optional and undecided.