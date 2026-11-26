"""目的の spec の子の承認（approve --queue --by-advisor）を、入口（autopilot.py の CLI）から通して確かめる。
子は、親が目的として承認され、自走の範囲の節が親と同じで、`- 親の要件:` の番号が全部親にあり、相談役 2 本の記録がそろうときだけ queued になる。"""
import json
import sys
import time

import pytest

from test_advisor_approval import OK_ADVISOR, OK_CHECKER, PREFIX, both_ran, out, subagent_ran
from test_autopilot import GOOD_SPEC, PLUGIN, init_spec, repo, run, state, user_says  # noqa: F401

sys.path.insert(0, str(PLUGIN / "scripts"))
import goal  # noqa: E402


def parent_goal(repo, slug="parent"):
    """人が 1 回承認した目的の spec（phase は discovery のまま）。"""
    d = init_spec(repo, slug)
    user_says(repo, prompt="目的 OK")
    r = run(repo, "approve", str(d), "--by", "目的 OK", "--goal")
    assert r.returncode == 0, out(r)
    return d


def child_spec(repo, parent, slug="child", reqs="R1、R2", extra="", scope_line=None):
    """親 spec・親の要件を書いた、discovery の子。scope_line を渡すと自走の範囲の節に 1 行足して親と違う節にする。"""
    d = init_spec(repo, slug)
    text = GOOD_SPEC.replace("- 大きさ: S", "- 大きさ: S" + (f"\n- 親 spec: {parent.name}" if parent else "") + (f"\n- 親の要件: {reqs}" if reqs else "") + extra)
    if scope_line:
        text = text.replace("- AWS の profile: なし", f"- AWS の profile: なし\n{scope_line}")
    (d / "spec.md").write_text(text, encoding="utf-8")
    time.sleep(0.02)  # 相談役の記録の時刻はミリ秒に切り捨てるので、spec.md の mtime より前にならないよう離す
    return d


def queue_by_advisor(repo, d, by="子 OK"):
    return run(repo, "approve", str(d), "--by", by, "--queue", "--by-advisor")


def test_child_is_queued_by_advisor_records_when_the_parent_is_a_goal(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 0, out(r)
    s = state(d)
    assert s["phase"] == "queued"
    assert s["approved_by"] == PREFIX + "子 OK"
    assert "goal" not in s
    assert state(parent)["phase"] == "discovery"


def test_goal_spec_naming_itself_as_its_parent_is_not_queued_as_a_child(repo):
    parent = parent_goal(repo)
    text = (parent / "spec.md").read_text(encoding="utf-8").replace("- 大きさ: S", f"- 大きさ: S\n- 親 spec: {parent.name}\n- 親の要件: R1、R2")
    (parent / "spec.md").write_text(text, encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    r = queue_by_advisor(repo, parent)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and "自分自身" in r.stdout, out(r)
    assert state(parent)["phase"] == "discovery"


def test_child_needs_no_human_prompt(repo):
    """子の承認は人の発言の代わりに相談役を受ける（人の発言は 1 つも無い）。"""
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    both_ran()
    assert queue_by_advisor(repo, d).returncode == 0


def test_child_without_a_parent_line_is_refused_and_stays_discovery(repo):
    parent_goal(repo)
    d = child_spec(repo, None, reqs=None)
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and "親 spec" in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


def test_child_whose_parent_directory_does_not_exist_is_refused(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace(parent.name, "2026-01-01-nothing"), encoding="utf-8")
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and "2026-01-01-nothing" in r.stdout and "目的として承認されていない" in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


def test_child_of_a_parent_that_was_not_approved_as_a_goal_is_refused(repo):
    parent = init_spec(repo, "parent")
    d = child_spec(repo, parent)
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and "目的として承認されていない" in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


def test_child_whose_scope_section_differs_from_the_parent_is_refused(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent, scope_line="- 通知: デスクトップ")
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and "自走の範囲" in r.stdout and "親" in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


@pytest.mark.parametrize("reqs, word", [
    ("R1、R3", "R3"),
    ("R9", "R9"),
    ("全部", "親の要件"),
    ("R1、", "親の要件"),
    (None, "親の要件"),
])
def test_child_with_a_requirement_the_parent_does_not_have_is_refused(repo, reqs, word):
    parent = parent_goal(repo)
    d = child_spec(repo, parent, reqs=reqs)
    both_ran()
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and word in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


@pytest.mark.parametrize("advisor, checker, word", [
    (None, OK_CHECKER, "fable-advisor"),
    (OK_ADVISOR, None, "advice-checker"),
    ("承認: 否\n", OK_CHECKER, "承認: 可"),
    (OK_ADVISOR, "判定: 反証あり（確かめられない 0 / 3）\n", "反証あり"),
    (OK_ADVISOR, "判定: 反証なし（確かめられない 1 / 3）\n", "確かめられない"),
])
def test_child_is_refused_when_an_advisor_condition_is_missing(repo, advisor, checker, word):
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    if advisor is not None:
        subagent_ran("fable-advisor", advisor)
    if checker is not None:
        subagent_ran("advice-checker", checker)
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and word in r.stdout, out(r)
    assert state(d)["phase"] == "discovery" and "approved_by" not in state(d)


def test_child_refusal_lists_every_missing_condition_at_once(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent, reqs="R1、R7", scope_line="- 通知: デスクトップ")
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1
    for word in ("R7", "自走の範囲", "fable-advisor", "advice-checker"):
        assert word in r.stdout, out(r)


def test_child_records_made_before_the_last_spec_change_do_not_count(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    both_ran()
    time.sleep(0.02)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    r = queue_by_advisor(repo, d)
    assert r.returncode == 1 and "spec.md の最後の変更" in r.stdout, out(r)


def test_second_child_needs_its_own_consultation_after_the_first_child_was_approved(repo):
    """先の子のための相談の記録で、相談していない後の子が通らない。"""
    parent = parent_goal(repo)
    first, second = child_spec(repo, parent, "first", "R1"), child_spec(repo, parent, "second", "R2")
    time.sleep(0.02)
    both_ran()
    assert queue_by_advisor(repo, first).returncode == 0
    r = queue_by_advisor(repo, second)
    assert r.returncode == 1 and "fable-advisor" in r.stdout and "advice-checker" in r.stdout, out(r)
    assert state(second)["phase"] == "discovery"
    time.sleep(0.02)
    both_ran()
    assert queue_by_advisor(repo, second).returncode == 0, out(r)
    assert state(second)["phase"] == "queued"


def test_a_child_of_another_parent_does_not_move_the_start_of_the_records(repo):
    parent, other = parent_goal(repo), parent_goal(repo, "other")
    a, b = child_spec(repo, parent, "a"), child_spec(repo, other, "b")
    time.sleep(0.02)
    both_ran()
    assert queue_by_advisor(repo, a).returncode == 0
    assert queue_by_advisor(repo, b).returncode == 0


def test_by_advisor_without_queue_still_refuses_a_discovery_spec(repo):
    parent = parent_goal(repo)
    d = child_spec(repo, parent)
    both_ran()
    r = run(repo, "approve", str(d), "--by", "子 OK", "--by-advisor")
    assert r.returncode == 1 and "人の返事が要る" in r.stdout, out(r)
    assert state(d)["phase"] == "discovery"


def test_child_requirements_parse_only_the_exact_form(repo):
    assert goal.parse_reqs("R1、R2") == ["R1", "R2"]
    assert goal.parse_reqs("R1") == ["R1"]
    assert goal.parse_reqs("R1、") is None
    assert goal.parse_reqs("R1 R2") is None
    assert goal.parse_reqs("") is None
