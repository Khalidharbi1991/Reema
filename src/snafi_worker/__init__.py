"""Snafi's PC worker: picks up jobs from the database mailbox, runs Ahmad's brain behind
its adapter, applies the permission gate and honesty check, and writes results back.

Every outside service sits behind an adapter chosen in worker.yaml (see registry.py).
"""

VERSION = "0.2.0"
