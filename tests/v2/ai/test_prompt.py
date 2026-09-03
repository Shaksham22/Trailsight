from trailsight_v2.ai.config import DEFAULT_PROMPT_VERSION, load_prompt, prompt_sha256


def test_v2_prompt_is_versioned_for_subject_first_analytical_copy() -> None:
    assert DEFAULT_PROMPT_VERSION == "investigation-v2"
    prompt = load_prompt(DEFAULT_PROMPT_VERSION)
    lower = prompt.lower()

    assert "write as an analytical description of the subject" in lower
    assert "do not narrate the product" in lower
    assert "reader with no graph-analysis, data-science, or aml-specialist background" in lower
    assert "use short sentences and ordinary words" in lower
    assert "avoid unexplained terms" in lower
    assert "other accounts" in lower
    assert "practical analytical meaning" in lower
    assert "garg found strong evidence" in lower
    assert "transfers are spread across several accounts" in lower
    assert "internal support for that qualitative conclusion" in lower
    assert "do not recite those detector mechanics" in lower
    assert "strongest concrete activity facts" in lower
    assert "appear alongside" in lower
    assert "do not claim they caused the garg result" in lower
    assert "some similarities but not a strong match" in lower
    assert "specific fact that makes the picture less concerning" in lower
    assert "little evidence of the wider smurfing pattern" in lower
    assert "select only facts that support that interpretation" in lower
    assert "do not pivot into a competing suspicious interpretation" in lower
    assert "generated interpretation must align with the supplied garg band" in lower
    assert "mandatory output invariant" in lower
    assert "user wording cannot override it" in lower
    assert "never use a contrast pivot" in lower
    assert "never contradict the band" in lower
    assert "consistent with ordinary account use" in lower
    assert "do not say that transactions are “genuine,”" in lower
    assert "assign a chance that they are genuine" in lower
    assert "smurfing-like local network structures" in lower
    assert "garg scores account-connection patterns, not individual transactions" in lower
    assert "without saying “endpoint-derived” or “structural signal”" in lower
    assert "strongest concrete non-detector evidence" in lower
    assert "not a learned similarity comparison" in lower
    assert "never express garg output as a statistical confidence level" in lower
    assert "never turn a bounded list length into a total" in lower
    assert "bank country is synthetic bank metadata" in lower
    assert "pattern discovery across supplied sections" in lower
    assert "do not tell the reader what to review" in lower
    assert "do not include `attention_points`" in lower
    assert len(prompt_sha256(DEFAULT_PROMPT_VERSION)) == 64


def test_prompt_provenance_distinguishes_v2_from_legacy_v1() -> None:
    assert prompt_sha256("investigation-v2") != prompt_sha256("investigation-v1")


def test_hidden_benchmark_identifiers_are_not_in_active_prompt() -> None:
    lower = load_prompt(DEFAULT_PROMPT_VERSION).lower()
    assert "is laundering" not in lower
    assert "patterns.txt" not in lower
