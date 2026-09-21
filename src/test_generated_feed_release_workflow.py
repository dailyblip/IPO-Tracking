from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _step_block(workflow_path: str, step_name: str) -> str:
    text = (ROOT / workflow_path).read_text(encoding="utf-8")
    marker = f"      - name: {step_name}\n"
    start = text.index(marker)
    next_step = text.find("\n      - name:", start + len(marker))
    if next_step == -1:
        next_step = len(text)
    return text[start:next_step]


def test_daily_generated_feed_release_gate_uses_full_pytest_suite():
    block = _step_block(
        ".github/workflows/daily.yml",
        "Run release-blocking regression suite on generated feed",
    )
    assert "python -m pytest src -q" in block
    assert "python -m unittest discover" not in block


def test_ownership_regenerated_feed_release_gate_uses_full_pytest_suite():
    block = _step_block(
        ".github/workflows/ownership-refresh.yml",
        "Run release-blocking regression suite on regenerated feed",
    )
    assert "python -m pytest src -q" in block
    assert "python -m unittest discover" not in block
