from pathlib import Path

from research.backtest_90d import CFG, END, START, run


def test_research_backtest_90d() -> None:
    result = run()

    assert result["run"]["primary_source"] == "data.binance.vision USD-M futures archives"
    assert result["run"]["period_start"] == START.isoformat()
    assert result["run"]["period_end_exclusive"] == END.isoformat()
    assert result["metrics"]["capital_start"] == CFG["capital_start"]
    assert isinstance(result["universe"], list)
    assert Path("research_backtest_result.json").is_file()
