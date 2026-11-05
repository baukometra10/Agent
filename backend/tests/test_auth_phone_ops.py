from pathlib import Path

from app.billing.entitlements import EntitlementStore
from app.config import Settings
from app.ops.monitor import OpsMonitor


def test_identity_email_and_phone_together(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    store = EntitlementStore(settings=settings)

    start = store.start_identity_login("member@example.com", "+491701234567")
    assert start["ok"] is True
    assert start.get("dev_email_code")
    assert start.get("dev_phone_code")

    verified = store.verify_identity_login(
        "member@example.com",
        "+491701234567",
        start["dev_email_code"],
        start["dev_phone_code"],
    )
    assert verified["ok"] is True
    assert verified["needs_second_factor"] is False
    assert verified["user"]["email_verified"] is True
    assert verified["user"]["phone_verified"] is True
    assert verified["user"]["session_token"]
    assert verified["user"]["phone"] == "+491701234567"


def test_admin_also_needs_email_and_phone(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        super_admin_email="boss@spixa.admin",
    )
    store = EntitlementStore(settings=settings)
    start = store.start_identity_login("boss@spixa.admin", "+491709999999")
    verified = store.verify_identity_login(
        "boss@spixa.admin",
        "+491709999999",
        start["dev_email_code"],
        start["dev_phone_code"],
    )
    assert verified["ok"] is True
    assert verified["needs_second_factor"] is False
    assert verified["user"]["access"] == "admin"
    assert verified["user"]["phone_verified"] is True


def test_failed_login_raises_alert(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    mon = OpsMonitor(settings=settings)
    for _ in range(5):
        alert = mon.record_failed_login("attacker@example.com")
    assert alert is not None
    assert alert["kind"] == "failed_login_burst"
    alerts = mon.list_alerts()
    assert any(a["kind"] == "failed_login_burst" for a in alerts)


def test_suspend_blocks_spend(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    store = EntitlementStore(settings=settings)
    start = store.start_login("u@example.com")
    store.verify_login("u@example.com", start["dev_code"])
    # force active without phone for spend path test
    data = store._load_users()
    data["users"]["u@example.com"]["phone_verified"] = True
    data["users"]["u@example.com"]["status"] = "active"
    store._save_users(data)
    store.set_user_status("u@example.com", "suspended", reason="test")
    spent = store.spend_tokens("u@example.com", 1, reason="chat")
    assert spent["ok"] is False
    assert spent["error"] == "account_blocked"
