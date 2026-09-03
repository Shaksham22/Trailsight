from pathlib import Path


def test_runtime_prompt_and_eval_scenarios_do_not_embed_hidden_dataset_identifiers() -> None:
    root = Path(__file__).resolve().parents[3]
    runtime_files = [
        root / "prompts" / "v2" / "investigation-v1.md",
        root / "prompts" / "v2" / "investigation-v2.md",
        root / "evals" / "v2" / "scenarios.yaml",
    ]
    for path in runtime_files:
        lower = path.read_text(encoding="utf-8").lower()
        assert "is laundering" not in lower
        assert "patterns.txt" not in lower
