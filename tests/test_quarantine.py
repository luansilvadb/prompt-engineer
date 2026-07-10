import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.quarantine_manager import (
    detect_flakiness,
    isolate_file,
    register_ticket,
    notify_pr,
    generate_report
)

def test_detect_flakiness_true():
    """Tests that detect_flakiness correctly identifies a test with inconsistent results as flaky."""
    # Mock run_pytest_on_target to return True on first run, False on second
    with patch("src.quarantine_manager.run_pytest_on_target") as mock_run:
        mock_run.side_effect = [
            (True, "Success output"),
            (False, "Fail output of run 2"),
            (True, "Success output"),
            (True, "Success output"),
            (True, "Success output"),
        ]
        is_flaky, pass_cnt, fail_cnt, logs = detect_flakiness("tests/dummy.py", max_runs=5)

        assert is_flaky is True
        assert pass_cnt == 4
        assert fail_cnt == 1
        assert len(logs) == 1
        assert "Fail output of run 2" in logs[0]

def test_detect_flakiness_false_all_pass():
    """Tests that detect_flakiness identifies a consistently passing test as non-flaky."""
    with patch("src.quarantine_manager.run_pytest_on_target") as mock_run:
        mock_run.side_effect = [
            (True, "Success"),
            (True, "Success"),
            (True, "Success"),
        ]
        is_flaky, pass_cnt, fail_cnt, logs = detect_flakiness("tests/dummy.py", max_runs=3)

        assert is_flaky is False
        assert pass_cnt == 3
        assert fail_cnt == 0
        assert len(logs) == 0

def test_detect_flakiness_false_all_fail():
    """Tests that detect_flakiness identifies a consistently failing test as non-flaky."""
    with patch("src.quarantine_manager.run_pytest_on_target") as mock_run:
        mock_run.side_effect = [
            (False, "Fail"),
            (False, "Fail"),
            (False, "Fail"),
        ]
        is_flaky, pass_cnt, fail_cnt, logs = detect_flakiness("tests/dummy.py", max_runs=3)

        assert is_flaky is False
        assert pass_cnt == 0
        assert fail_cnt == 3
        assert len(logs) == 3

def test_isolate_file(tmp_path):
    """Tests that isolate_file moves the test file and prepends the correct quarantine comment."""
    src_file = tmp_path / "test_flaky_example.py"
    dest_dir = tmp_path / "quarantine"

    test_code = "def test_foo():\n    assert True\n"
    src_file.write_text(test_code, encoding="utf-8")

    reason = "Alternating pass/fail results"
    dest_file = isolate_file(str(src_file), str(dest_dir), reason)

    # Check old file is deleted and new file exists
    assert not src_file.exists()
    assert os.path.exists(dest_file)

    # Check comment contents at the top
    with open(dest_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) > 1
    # Check for correct spelling of 'identado'
    assert "// QUARENTENA: Teste flaky identado em" in lines[0]
    assert reason in lines[0]
    assert "def test_foo():" in lines[1]

def test_register_ticket(tmp_path):
    """Tests that register_ticket produces valid metadata, labels, and updates the local registry."""
    # Mocking registry path to not affect real files
    with patch("os.makedirs"), patch("json.dump") as mock_json_dump, patch("os.path.exists", return_value=False):
        ticket = register_ticket("tests/test_some_file.py::test_case", ["Failure logs detailed"])

        assert ticket["title"] == "[FLAKY-TEST] tests/test_some_file.py::test_case"
        assert "flaky" in ticket["labels"]
        assert "quarentena" in ticket["labels"]
        assert "tech-debt" in ticket["labels"]
        assert ticket["commit_hash"] != ""
        assert ticket["environment"] != ""
        assert "Failure logs detailed" in ticket["fail_log"]
        assert "reproduction_steps" in ticket
        assert "url" in ticket

def test_notify_pr():
    """Tests that notify_pr returns correctly formatted warning comments for the PR/MR."""
    comment, pr_url = notify_pr(
        test_name="tests/test_example.py",
        fail_count=3,
        ticket_url="https://github.com/mock/issues/12",
        custom_pr_url="https://github.com/mock/pull/1#issuecomment-999"
    )

    assert comment == "⚠️ Teste tests/test_example.py movido para quarentena após 3 falhas intermitentes. Ticket: https://github.com/mock/issues/12."
    assert pr_url == "https://github.com/mock/pull/1#issuecomment-999"

def test_generate_report():
    """Tests that generate_report outputs the expected markdown report format."""
    report = generate_report(
        test_name="tests/test_example.py",
        src_path="tests/test_example.py",
        dest_path="tests/quarantine/test_example.py",
        fail_count=2,
        ticket_url="https://github.com/mock/issues/12",
        pr_url="https://github.com/mock/pull/1#issuecomment-999",
        ci_status="stable"
    )

    assert "## Relatório de Quarentena" in report
    assert "- Teste: tests/test_example.py" in report
    assert "- Arquivo movido: tests/test_example.py → tests/quarantine/test_example.py" in report
    assert "- Falhas registradas: 2 intermitências" in report
    assert "- Ticket criado: https://github.com/mock/issues/12" in report
    assert "- PR notificado: https://github.com/mock/pull/1#issuecomment-999" in report
    assert "- Status do CI: stable" in report
    assert "- Próxima revisão sugerida:" in report
