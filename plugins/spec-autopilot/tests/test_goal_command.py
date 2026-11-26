"""commands/autopilot.md の A の 3 の L の項（目的の spec の手順）が書く subcommand と引数が、
argparse の定義で通ることと、版数が上がったことを確かめる（コードが読む値と文書の突き合わせ）。"""
import json
import re
import shlex
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import autopilot as ap  # noqa: E402
import goal  # noqa: E402
import lineup  # noqa: E402

DOC = PLUGIN / "commands" / "autopilot.md"
MARKER = "**目的の spec（人が 1 回承認し、夜の間に子へ分ける）**"


def goal_bullet():
    lines = [x for x in DOC.read_text(encoding="utf-8").splitlines() if MARKER in x]
    assert len(lines) == 1, "A の 3 の L の項に目的の spec の手順が 1 つだけ要る"
    return lines[0]


def invocations():
    """手順の code span のうち、`CLI ...` と `lineup.py ...` の呼び出し。<..> は x に置き換える。"""
    spans = re.findall(r"`([^`]+)`", goal_bullet())
    out = []
    for sp in spans:
        m = re.match(r"(CLI|lineup\.py) (.+)", sp)
        if m:
            out.append((m.group(1), shlex.split(re.sub(r"<[^>]*>", "x", m.group(2)))))
    return out


def test_goal_procedure_names_the_subcommands_in_order():
    calls = [(w, a[0], [x for x in a if x.startswith("--")]) for w, a in invocations()]
    assert calls == [
        ("CLI", "approve", ["--by", "--goal"]),
        ("CLI", "init", []),
        ("CLI", "approve", ["--by", "--queue", "--by-advisor"]),
        ("lineup.py", "next", []),
        ("CLI", "goal", []),
    ]


def test_goal_procedure_invocations_parse_with_the_real_argparse(monkeypatch):
    seen = []
    monkeypatch.setattr(ap, "cmd_approve", lambda a: seen.append(a) or 0)
    monkeypatch.setattr(ap, "cmd_init", lambda a: seen.append(a) or 0)
    monkeypatch.setattr(goal, "cmd", lambda a: seen.append(a) or 0)
    monkeypatch.setattr(lineup, "cmd_next", lambda a: seen.append(a) or 0)
    for who, argv in invocations():
        (ap.main if who == "CLI" else lineup.main)(argv)
    approve_goal, _, approve_child, _, goal_a = seen[0], seen[1], seen[2], seen[3], seen[4]
    assert approve_goal.goal and not approve_goal.queue and not approve_goal.by_advisor
    assert approve_child.queue and approve_child.by_advisor and not approve_child.goal
    assert goal_a.cmd == "goal"


def test_goal_procedure_names_what_the_morning_report_needs():
    b = goal_bullet()
    for word in ("approved_by", "goal の結果", "fable-advisor", "advice-checker", "B の 1〜3", "- 親 spec:", "- 親の要件:"):
        assert word in b, word


def test_version_is_raised_past_0_1_7():
    v = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    assert tuple(int(x) for x in v.split(".")) > (0, 1, 7)
