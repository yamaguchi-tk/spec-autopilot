"""playbook の external-service・iac が示す前提の書き方の例を、spec の「## 前提」に写して lint に通す（R3）。"""
import re
import textwrap

import pytest

from test_autopilot import GOOD_SPEC, PLUGIN, repo  # noqa: F401（repo は fixture）
from test_stages import lint

NONE_PREMISE = "- 前提: なし（新しく作るので、頼る既存の振る舞いが無い）\n"
FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)


def example_lines(name):
    text = (PLUGIN / "references" / "playbooks" / f"{name}.md").read_text(encoding="utf-8")
    return "".join(textwrap.dedent(b) for b in FENCE.findall(text) if "- 前提:" in b)


@pytest.mark.parametrize("name", ["external-service", "iac"])
def test_the_premise_example_in_the_playbook_passes_lint(repo, name):
    example = example_lines(name)
    assert "（確認日 " in example and "  - URL: " in example, f"{name} に前提の例（確認日つき・URL の行つき）が無い"
    assert NONE_PREMISE in GOOD_SPEC
    r = lint(repo, GOOD_SPEC.replace(NONE_PREMISE, example))
    assert r.returncode == 0, r.stdout
