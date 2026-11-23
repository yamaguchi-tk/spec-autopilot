"""spec-autopilot に同梱した判断の相談役 2 本（opus-advisor・fable-advisor）が、GDD を入れずに使える形かを確かめる。

1. agent の定義の front matter（name・model・effort・tools）が、相談役として決めた値になっている
"""
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]


def _front(path):
    head = path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    return dict(re.findall(r"^(\w+): (.+)$", head, re.M))


# ---- 1. agent の定義 ----

@pytest.mark.parametrize(
    "agent, model, effort",
    [("opus-advisor", "opus", "high"), ("fable-advisor", "fable", "medium")],
)
def test_agent_front_matter(agent, model, effort):
    front = _front(PLUGIN / "agents" / f"{agent}.md")
    assert (front["name"], front["model"], front["effort"]) == (agent, model, effort)
    assert front["tools"] == "Read, Grep, Glob"
    assert front["omitClaudeMd"] == "true"
