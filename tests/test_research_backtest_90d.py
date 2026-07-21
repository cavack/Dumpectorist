from pathlib import Path

from research.backtest_90d import CFG, run


def test_research_backtest_90d() -> None:
    result = run()

    assert result["universe"]
    assert result["run"]["http_requests"] > 0
    assert result["metrics"]["capital_start"] == CFG["capital_start"]
    assert Path("research_backtest_result.json").is_file()
