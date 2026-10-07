import math

from app.services.embeddings import HashEmbedding, book_text


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_dimension_and_unit_norm():
    vec = HashEmbedding(384).embed(["microservices with kafka"])[0]
    assert len(vec) == 384
    assert math.isclose(sum(v * v for v in vec), 1.0, rel_tol=1e-6)


def test_deterministic():
    p = HashEmbedding(64)
    assert p.embed(["same text"]) == p.embed(["same text"])


def test_related_text_scores_higher_than_unrelated():
    p = HashEmbedding(384)
    query, related, unrelated = p.embed([
        "dragon quest adventure",
        "a quest to reclaim treasure from a dragon",
        "agile software craftsmanship and clean code",
    ])
    assert cosine(query, related) > cosine(query, unrelated)


def test_book_text_includes_all_parts():
    text = book_text("Dune", ["Frank Herbert"], "Desert planet")
    assert "Dune" in text and "Frank Herbert" in text and "Desert planet" in text
