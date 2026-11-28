"""autopilot.py init が、手元の設定 models.md を作る spec.md の `## モデル` 節に写すことを、CLI の入口から確かめる。"""
import os
import re
from pathlib import Path

import pytest

from test_autopilot import repo, run  # noqa: F401（repo は fixture）

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "spec.md"
LADDER = Path(__file__).resolve().parents[1] / "scripts" / "ladder.py"


def models_md():
    return Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "models.md"


def put(content):
    p = models_md()
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        content = content.encode("utf-8")
    p.write_bytes(content)


def init(repo, slug="game"):
    r = run(repo, "init", slug)
    assert r.returncode == 0, r.stdout + r.stderr
    d = Path(r.stdout.strip())
    return d, (d / "spec.md").read_text(encoding="utf-8"), r.stderr


def model_section(text):
    return re.search(r"^## モデル\n(.*?)(?=^## )", text, re.M | re.S).group(1)


def test_init_copies_the_local_setting_after_the_template_comment_and_notes_it(repo):
    put("- 実装: opus-medium\n- 評価: opus-xhigh\n")
    d, text, err = init(repo)
    sec = model_section(text)
    comment = re.match(r"<!--.*?-->\n", sec, re.S).group(0)
    assert sec[len(comment):].startswith("- 実装: opus-medium\n- 評価: opus-xhigh\n")
    assert re.search(r"NOTE.*- 実装: opus-medium.*- 評価: opus-xhigh", err, re.S), err
    lint = run(repo, "lint", str(d)).stdout
    assert not re.search(r"ERROR.*モデル", lint), lint


def test_init_copies_only_the_row_the_setting_has_and_keeps_the_rest_of_the_template(repo):
    put("- 評価: fable\n")
    _, text, _ = init(repo)
    template = TEMPLATE.read_text(encoding="utf-8")
    assert text.replace("- 評価: fable\n", "", 1) == template
    assert "- 実装:" not in model_section(text)


def test_init_without_a_local_setting_writes_the_template_as_it_is(repo):
    _, text, err = init(repo)
    assert text == TEMPLATE.read_text(encoding="utf-8")
    assert "NOTE: 手元の設定" not in err


@pytest.mark.parametrize("content", [
    "- 実装: haiku\n",
    "- 評価: sonnet-high\n",
    "- 実装: opus-medium\n- 実装: fable\n",
    "実装は opus-medium\n",
    b"- \xff\xfe\n",
])
def test_init_with_an_unreadable_setting_keeps_the_template_and_notes_the_fix(repo, content):
    put(content)
    _, text, err = init(repo)
    assert text == TEMPLATE.read_text(encoding="utf-8")
    assert "NOTE" in err and "ladder.py setup" in err and "ladder.py setup --reset" in err, err
    assert str(models_md()) in err


def test_init_leaves_the_setting_file_as_it_was_and_later_specs_follow_a_changed_setting(repo):
    put("- 実装: fable\n")
    _, first, _ = init(repo, "one")
    put("- 実装: opus-xhigh\n")
    _, second, _ = init(repo, "two")
    assert "- 実装: fable\n" in first and "- 実装: opus-xhigh\n" not in first
    assert "- 実装: opus-xhigh\n" in second
    assert models_md().read_text(encoding="utf-8") == "- 実装: opus-xhigh\n"


def test_init_copies_the_rows_in_the_order_and_form_the_file_has(repo):
    put("<!-- 手元の設定 -->\n- 評価:   opus-xhigh  \n- 実装: sonnet-high\n")
    _, text, _ = init(repo)
    assert re.search(r"-->\n- 評価: opus-xhigh\n- 実装: sonnet-high\n", model_section(text))


def test_init_does_not_copy_the_advisor_and_checker_rows_and_lint_stays_clean(repo):
    put("- 実装: opus-medium\n- 相談: opus-high\n- 検証: fable-high\n- 照合: opus-high\n")
    d, text, err = init(repo)
    sec = model_section(text)
    assert "- 実装: opus-medium\n" in sec and "相談" not in sec and "検証" not in sec and "照合" not in sec
    assert "相談" not in err and "検証" not in err and "照合" not in err and "誤り" not in err, err
    lint = run(repo, "lint", str(d)).stdout
    assert not re.search(r"ERROR.*モデル", lint), lint


def test_init_with_only_advisor_rows_writes_the_template_as_it_is(repo):
    put("- 相談: fable-high\n")
    _, text, err = init(repo)
    assert text == TEMPLATE.read_text(encoding="utf-8")
    assert "NOTE: 手元の設定" not in err
