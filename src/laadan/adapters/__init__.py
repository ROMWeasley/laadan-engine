"""Laadan Adapters Layer (Ports & Adapters Architecture).

Technical adapters that connect the application to the outside world:
- inbound: `web` (FastAPI app, security headers, origin checks, static files, client script)
- outbound: `models` (mock gateway and OpenAI-compatible HTTP gateway)
- outbound: `storage` (SQLite entity store and page store)
"""
