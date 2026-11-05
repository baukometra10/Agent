from app.activity import get_activity_bus


def test_activity_bus_emit_and_focus():
    bus = get_activity_bus()
    ev = bus.emit(
        "think",
        "hello",
        detail="world",
        project_id="00000000-0000-0000-0000-000000000001",
        project_name="Demo",
        intensity=0.8,
    )
    assert ev.id >= 1
    assert bus.recent(limit=5)
    focus = bus.focus()
    assert focus["project_name"] == "Demo"
    assert focus["active"] is True
