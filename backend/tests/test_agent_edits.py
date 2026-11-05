from app.workspace.edits import parse_agent_edits


def test_parse_fenced_path_and_spixa_block():
    reply = """
Here is the fix:

```src/app.py
print("spixa")
```

And another:

<<<SPIXA_EDIT notes.md>>>
# hi
<<<END_SPIXA_EDIT>>>
"""
    edits = parse_agent_edits(reply)
    paths = {e["path"] for e in edits}
    assert "src/app.py" in paths
    assert "notes.md" in paths
    app = next(e for e in edits if e["path"] == "src/app.py")
    assert "spixa" in app["content"]


def test_parse_hash_heading_files_with_bodies():
    reply = """
# README.md
Hello app

# main.py
print(1)

# spixa_edit
"""
    edits = parse_agent_edits(reply)
    paths = {e["path"] for e in edits}
    assert paths == {"README.md", "main.py"}
    assert "Hello" in next(e for e in edits if e["path"] == "README.md")["content"]


def test_ignore_empty_hash_filename_spam():
    reply = "\n".join(
        [
            "# README.md",
            "# Main.py",
            "# golden/spixa-golden-1.py",
            "# spixa_edit",
            "# README.md",
            "# Main.py",
        ]
    )
    assert parse_agent_edits(reply) == []


def test_stripe_dev_simulate_unlock(tmp_path):
    from app.billing.entitlements import EntitlementStore
    from app.billing.stripe_checkout import StripeCheckout
    from app.config import Settings

    settings = Settings(
        learning_data_root=tmp_path / "learning",
        stripe_secret_key="",  # force dev simulate
    )
    store = EntitlementStore(settings=settings)
    start = store.start_login("pay@example.com")
    store.verify_login("pay@example.com", start["dev_code"])
    stripe = StripeCheckout(settings=settings)
    out = stripe.create_checkout_session(email="pay@example.com", plan="pro")
    assert out["ok"] is True
    assert out["mode"] == "dev_simulate"
    assert "execution" in out["user"]["entitlements"]
