from app.memory.embeddings_store import cosine, local_embed


def test_local_embed_similarity_ranks_related_text():
    a = local_embed("project isolation namespace memory embeddings")
    b = local_embed("keep embeddings isolated per project namespace")
    c = local_embed("unrelated cooking recipe with pasta sauce")
    assert cosine(a, b) > cosine(a, c)
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_language_pack_phase37_count():
    from app.intelligence.languages import LANGUAGE_PACKS, EXT_TO_LANGUAGE

    names = {p.name for p in LANGUAGE_PACKS}
    assert "Zig" in names
    assert "Solidity" in names
    assert "GraphQL" in names
    assert EXT_TO_LANGUAGE.get(".zig") == "Zig"
    assert EXT_TO_LANGUAGE.get(".sol") == "Solidity"
    assert len(LANGUAGE_PACKS) >= 40
