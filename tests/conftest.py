from pathlib import Path


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # noqa: ARG001
    result_path = Path("research_backtest_result.json")
    if not result_path.is_file():
        return

    payload = result_path.read_text(encoding="utf-8").replace("\n", "")
    terminalreporter.write_sep("=", "RESEARCH BACKTEST RESULT")
    terminalreporter.write_line("RESEARCH_BACKTEST_RESULT_BEGIN")
    for offset in range(0, len(payload), 8_000):
        terminalreporter.write_line(payload[offset : offset + 8_000])
    terminalreporter.write_line("RESEARCH_BACKTEST_RESULT_END")
