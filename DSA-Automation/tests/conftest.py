import os
import sys

# Dummy values so modules import without a real database or API keys.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("REVIEW_PASSWORD", "pw")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
