from app.intelligence.ecosystem import SPIXA_FAMILY, ecosystem_blueprint


def test_six_specialties_and_non_goal():
    bp = ecosystem_blueprint()
    assert bp["adopted"] is True
    assert len(bp["family"]) == 6
    assert len(SPIXA_FAMILY) == 6
    assert bp["non_goal"]["train_huge_foundation_from_scratch_as_success_gate"] is False
    assert len(bp["roadmap"]) == 6
    assert bp["roadmap"][0]["id"] == "I1"
    assert bp["orchestrator"]["name"] == "Spixa Intelligence Orchestrator"
    products = {row["product"] for row in bp["family"]}
    assert "Spixa Coder" in products
    assert "Spixa Architect" in products
