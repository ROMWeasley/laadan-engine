"""Model Gateway Adapters.

Outbound adapters for language model providers:
- MockModelGateway (local fixtures for offline development and tests, including hostile outputs)
- Remote HTTP gateway (OpenAI-compatible structured output endpoints)

Gateways return raw text only. Parsing and validation happen in the compiler.
"""
