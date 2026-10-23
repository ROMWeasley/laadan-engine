"""Laadan Adapters Layer (Ports & Adapters Architecture).

Houses all inbound and outbound technical adapters that interface with the external world:
- inbound: `web` (FastAPI ASGI gateway, routes, and static assets)
- outbound: `models` (Mock and external model gateways)
- outbound: `storage` (SQLite and in-memory persistence)
- outbound: `security` (nh3 AST-level HTML sanitization)
"""
