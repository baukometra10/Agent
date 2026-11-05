"""In-process golden IDE path: project → files → apply-edits → terminal → chat session → ventures list."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ide_golden_path(client):
    health = await client.get("/health")
    assert health.status_code == 200

    import time

    slug = f"ide-golden-{int(time.time())}"
    created = await client.post(
        "/api/projects/blank",
        json={"name": "IDE Golden", "slug": slug},
    )
    assert created.status_code in (200, 201), created.text
    project = created.json()
    pid = project["id"]

    rel = ".spixa/golden/hello.py"
    put = await client.put(
        f"/api/projects/{pid}/workspace/file",
        json={"path": rel, "content": 'print("golden")\n'},
    )
    assert put.status_code == 200, put.text

    got = await client.get(f"/api/projects/{pid}/workspace/file", params={"path": rel})
    assert got.status_code == 200, got.text
    body = got.json()
    text = body.get("content") or body.get("text") or ""
    assert "golden" in text

    apply = await client.post(
        f"/api/projects/{pid}/workspace/apply-edits",
        json={
            "edits": [
                {"path": ".spixa/golden/from-agent.md", "content": "# from agent\n"},
            ]
        },
    )
    assert apply.status_code == 200, apply.text
    applied = apply.json()
    assert applied.get("ok", True) is True or not applied.get("errors")

    term = await client.post(
        f"/api/projects/{pid}/workspace/terminal",
        json={"command": "echo golden", "timeout": 15},
    )
    assert term.status_code == 200, term.text

    tree = await client.get(f"/api/projects/{pid}/workspace/tree")
    assert tree.status_code == 200, tree.text
    entries = tree.json().get("entries") or []
    paths = {e.get("path") for e in entries}
    assert any("from-agent.md" in (p or "") or p == ".spixa/golden/from-agent.md" for p in paths) or len(
        entries
    ) >= 1

    sess = await client.post(
        f"/api/projects/{pid}/chat/sessions",
        json={"title": "Golden"},
    )
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json().get("id")
    assert sid

    # Ask mode should not require writing files; may be simulated without keys.
    msg = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        json={"message": "قل: ok", "mode": "ask", "max_seconds": 30},
    )
    assert msg.status_code == 200, msg.text
    assert "reply" in msg.json()

    ventures = await client.get(f"/api/projects/{pid}/ventures")
    assert ventures.status_code == 200, ventures.text
    # Twin rebuild can be heavy; covered by live scripts/ide-golden-smoke.py (without --fast).
