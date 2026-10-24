"""Executa somente testes isolados. Nunca usa a DATABASE_URL de produção."""
import os
import pathlib
import secrets
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = ""
os.environ["RENDER"] = ""
os.environ["ADMIN_USERNAME"] = "local-test"
os.environ["ADMIN_PASSWORD"] = secrets.token_urlsafe(24)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)

suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
