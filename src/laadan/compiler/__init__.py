"""Laadan Compiler (security core).

Turns validated domain objects into HTML and checks the result:
- render: application-owned Jinja2 templates with autoescaping
- sanitize: nh3 (Rust ammonia) for RichText fragments only
- verify: selectolax (lexbor) output check before delivery

Every byte of HTML that reaches a browser passes through this package.
No network, storage, or model access.
"""
