from trailsight_v2.ai.config import DEFAULT_PROMPT_VERSION, load_prompt, prompt_sha256


def test_frozen_prompt_version_and_required_product_rules() -> None:
    assert DEFAULT_PROMPT_VERSION == "investigation-v1"
    prompt = load_prompt(DEFAULT_PROMPT_VERSION)
    lower = prompt.lower()
    assert "high review band does not mean laundering" in lower
    assert "low review band does not mean safe" in lower
    assert "synthetic bank metadata" in lower
    assert "not customer residence" in lower
    assert "evidence v2" in lower
    assert "one-hop only" in lower
    assert "source of funds" in lower
    assert len(prompt_sha256(DEFAULT_PROMPT_VERSION)) == 64


def test_hidden_benchmark_identifiers_are_not_in_prompt() -> None:
    lower = load_prompt(DEFAULT_PROMPT_VERSION).lower()
    assert "is laundering" not in lower
    assert "patterns.txt" not in lower
