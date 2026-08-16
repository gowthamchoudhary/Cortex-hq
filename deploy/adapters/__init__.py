"""Platform adapters for the Cortex agent runtime.

Each adapter receives an inbound message from its platform, calls
``deploy.agent_runtime.handle_incoming_message`` — the single reasoning entry
point — and posts the formatted reply back to the platform. Live outbound
calls are isolated in ``post_*``/``send_*`` functions that only fire when the
platform's env-var token is configured.
"""
