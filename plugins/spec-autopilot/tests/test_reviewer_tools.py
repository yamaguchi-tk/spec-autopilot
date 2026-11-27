"""評価役の定義（autopilot-reviewer と梯子の段 2 つ）の front matter の tools に、自分で起こした処理を止める TaskStop があるかを確かめる。

host が読むのは front matter の tools なので、そこだけを見る（本文の文言は assert しない）。
"""
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]


def _front(path):
    head = path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    return dict(re.findall(r"^(\w+): (.+)$", head, re.M))


@pytest.mark.parametrize("agent", ["autopilot-reviewer", "autopilot-reviewer-xhigh", "autopilot-reviewer-fable"])
def test_reviewer_tools_include_taskstop_and_keep_the_rest(agent):
    tools = [t.strip() for t in _front(PLUGIN / "agents" / f"{agent}.md")["tools"].split(",")]
    assert "TaskStop" in tools
    assert {"Read", "Grep", "Glob", "Bash", "Write"} <= set(tools)
