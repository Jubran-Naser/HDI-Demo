"""Shared test setup. Tests never call a real AI model, so they run anywhere in seconds (also on GitHub)."""

import os
import tempfile

# Before the service's code is loaded: the endpoint tests save their audit records in a throwaway database
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test-audit.db"
