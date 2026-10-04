import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.github_webhook import verify_github_signature
from app.services.dsa_structure_service import DSAStructureService
from app.services import notification_service

client = TestClient(app)


def _sign(body: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_valid():
    body = b'{"a": 1}'
    assert verify_github_signature(body, _sign(body))


def test_signature_wrong_secret_rejected():
    body = b'{"a": 1}'
    assert not verify_github_signature(body, _sign(body, "other"))


def test_signature_missing_rejected():
    assert not verify_github_signature(b"{}", None)


def test_webhook_rejects_bad_signature():
    r = client.post(
        "/webhooks/github",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=bad", "X-GitHub-Event": "push"},
    )
    assert r.status_code == 401


def test_health_is_public():
    assert client.get("/health").json() == {"status": "ok"}


def test_review_requires_auth():
    assert client.get("/review").status_code == 401


def test_backfill_requires_auth():
    assert client.post("/webhooks/backfill/generate").status_code == 401


def test_taxonomy_built_from_repo_tree():
    tree = [
        {"path": "Arrays", "type": "tree"},
        {"path": "Arrays/Two Pointers", "type": "tree"},
        {"path": "Binary Search", "type": "tree"},
        {"path": "README.md", "type": "blob"},
    ]
    result = DSAStructureService.build_taxonomy(tree)
    assert result["topics"] == ["Arrays", "Binary Search"]
    assert result["patterns"]["Arrays"] == ["Two Pointers"]


@pytest.mark.asyncio
async def test_notification_skipped_without_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert await notification_service.notify_draft_ready(1, "Two Sum") is False


def test_review_url_uses_public_base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com/")
    assert notification_service.build_review_url(5) == "https://example.com/review/5"
# ---------------- hardening tests ----------------
import base64

from app import security


def _basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


@pytest.fixture(autouse=True)
def _clean_lockout():
    security.reset_failures()
    yield
    security.reset_failures()


@pytest.fixture
def fast_delay(monkeypatch):
    monkeypatch.setattr(security, "FAILURE_DELAY_SECONDS", 0)


def test_docs_are_disabled():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_security_headers_present():
    r = client.get("/health")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_wrong_password_rejected(fast_delay):
    assert client.get("/review", headers=_basic("admin", "nope")).status_code == 401


def test_lockout_after_repeated_failures(fast_delay):
    for _ in range(security.MAX_FAILURES):
        assert client.get("/review", headers=_basic("admin", "bad")).status_code == 401
    assert client.get("/review", headers=_basic("admin", "pw")).status_code == 429


def test_cross_site_post_blocked():
    r = client.post(
        "/review/1/approve",
        headers={**_basic("admin", "pw"), "Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_null_origin_post_blocked():
    r = client.post(
        "/review/1/approve",
        headers={**_basic("admin", "pw"), "Origin": "null"},
    )
    assert r.status_code == 403