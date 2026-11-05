from pathlib import Path

from app.billing.entitlements import EntitlementStore
from app.config import Settings


def test_login_and_payment_unlock(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        super_admin_email="boss@evolve.admin",
    )
    store = EntitlementStore(settings=settings)
    start = store.start_login("member@example.com")
    assert start["ok"] is True
    code = start["dev_code"]
    verified = store.verify_login("member@example.com", code)
    assert verified["ok"] is True
    assert verified["user"]["access"] == "user"
    assert verified["user"]["plan"] == "free"

    paid = store.confirm_payment(
        email="member@example.com",
        plan="pro",
        provider_ref="pay_test_1",
        amount=29.0,
    )
    assert paid["ok"] is True
    assert paid["user"]["plan"] == "pro"
    assert "chat" in paid["user"]["entitlements"]
    assert paid["user"]["tokens_remaining"] == 5000


def test_admin_email_gets_admin_access(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        super_admin_email="boss@evolve.admin",
    )
    store = EntitlementStore(settings=settings)
    start = store.start_login("boss@evolve.admin")
    verified = store.verify_login("boss@evolve.admin", start["dev_code"])
    assert verified["user"]["access"] == "admin"


def test_usage_ledger_after_spend(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    store = EntitlementStore(settings=settings)
    start = store.start_login("u@example.com")
    store.verify_login("u@example.com", start["dev_code"])
    spent = store.spend_tokens("u@example.com", 3, reason="test_task")
    assert spent["ok"] is True
    report = store.usage_report("u@example.com")
    assert report["tokens_spent_logged"] >= 3
    assert len(report["events"]) >= 1
    assert isinstance(report.get("daily"), list)
    assert isinstance(report.get("by_reason"), list)


def test_free_plan_locks_execution_until_payment(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    store = EntitlementStore(settings=settings)
    start = store.start_login("member@example.com")
    verified = store.verify_login("member@example.com", start["dev_code"])
    feats = verified["user"]["entitlements"]
    assert "chat" in feats
    assert "execution" not in feats
    paid = store.confirm_payment(
        email="member@example.com", plan="pro", provider_ref="test-pay"
    )
    assert paid["ok"] is True
    assert "execution" in paid["user"]["entitlements"]
    assert paid["user"]["tokens_monthly"] == 5000
