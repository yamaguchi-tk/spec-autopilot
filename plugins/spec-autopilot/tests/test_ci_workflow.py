"""CI の workflow と CLAUDE.md のテストの行を、コードが読む値として確かめる。

- workflow の pip install は、入れる道具をどれも `==` で版を固定する
- workflow の pytest は `-n auto` で並列に回す
- CLAUDE.md のテストのコマンドも `-n auto` 付きで、道具は workflow の行を回すと書き、版の数字は書かない
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
CLAUDE_MD = (REPO / "CLAUDE.md").read_text(encoding="utf-8")


def _run_lines(text):
    return [m.group(1).strip() for m in re.finditer(r"^\s*run:\s*(.+)$", text, re.M)]


def test_workflow_pins_every_pip_installed_tool_with_double_equals():
    installs = [r for r in _run_lines(WORKFLOW) if "pip install" in r]
    assert len(installs) == 1
    tools = installs[0].split("pip install", 1)[1].split()
    assert {t.split("==")[0] for t in tools} == {"pytest", "pytest-xdist", "execnet"}
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==\d+(\.\d+)*", t) for t in tools), tools


def test_workflow_runs_pytest_in_parallel_with_n_auto():
    runs = [r for r in _run_lines(WORKFLOW) if "pytest plugins/spec-autopilot/tests/" in r]
    assert len(runs) == 1
    assert re.search(r"(^|\s)-n auto(\s|$)", runs[0])


def test_claude_md_test_command_uses_n_auto_and_points_to_the_workflow_install_line():
    cmd = next(l for l in CLAUDE_MD.splitlines() if "python3 -m pytest" in l)
    assert re.search(r"(^|\s)-n auto(?![\w-])", cmd)
    assert "pip install" in cmd and ".github/workflows/test.yml" in cmd


def test_claude_md_has_no_tool_version_numbers():
    assert not re.search(r"==\s*\d|\b\d+\.\d+\.\d+\b", CLAUDE_MD)
