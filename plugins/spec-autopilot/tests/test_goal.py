"""目的の spec の承認（approve --goal）を、入口（autopilot.py の CLI）から通して確かめる。
人が目的の spec を 1 回承認すると、大きさ L でも止まらず、目的として承認した記録だけが残る（phase は discovery のまま）。"""
import json
import subprocess
import sys

import pytest

from test_autopilot import GOOD_SPEC, PLUGIN, approved, existing_spec, init_spec, repo, run, state, stop_hook, user_says, write_files  # noqa: F401
from test_size import six_changed_files

sys.path.insert(0, str(PLUGIN / "scripts"))
import goal  # noqa: E402

OVERNIGHT = PLUGIN / "scripts" / "overnight.py"


def large_goal(repo):
    """申告 L・変えるファイルが 6 つ以上の、既存の repo の目的の spec。"""
    d = existing_spec(repo, size="- 大きさ: L")
    six_changed_files(repo)
    return d


def goal_approve(repo, d, by="目的 OK", *extra, say=True):
    if say:
        user_says(repo, prompt=by)
    return run(repo, "approve", str(d), "--by", by, "--goal", *extra)


def test_approve_goal_records_the_goal_and_keeps_discovery_for_a_large_spec(repo):
    d = large_goal(repo)
    r = goal_approve(repo, d, "目的 OK")
    assert r.returncode == 0, r.stdout + r.stderr
    s = state(d)
    assert s["phase"] == "discovery"
    assert s["goal"]["by"] == "目的 OK"
    assert isinstance(s["goal"]["at"], float)
    assert len(s["goal"]["scope_sha256"]) == 64
    assert not {"approved_at", "approved_by", "budget_min"} & set(s)


def test_approve_without_goal_still_stops_a_large_spec(repo):
    d = large_goal(repo)
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 1
    assert "大きさ L の spec は 1 本のまま合意しない" in r.stdout
    assert "goal" not in state(d)


def test_approve_goal_accepts_a_declared_large_spec_in_a_new_repo(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- 大きさ: S", "- 大きさ: L"), encoding="utf-8")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 1
    r = goal_approve(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["phase"] == "discovery" and "goal" in state(d)


def test_approve_goal_still_stops_at_other_lint_errors(repo):
    d = large_goal(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 予算:", "- 予算の行を消した:"), encoding="utf-8")
    r = goal_approve(repo, d)
    assert r.returncode == 1
    assert "予算が無い" in r.stdout
    assert "goal" not in state(d)


def test_approve_goal_needs_a_human_prompt_after_the_last_spec_change(repo):
    d = large_goal(repo)
    r = goal_approve(repo, d, say=False)
    assert r.returncode != 0
    assert "人の発言" in r.stdout + r.stderr
    assert "goal" not in state(d)


@pytest.mark.parametrize("flag", ["--queue", "--by-advisor"])
def test_approve_goal_refuses_to_combine_with_queue_or_advisor(repo, flag):
    d = large_goal(repo)
    r = goal_approve(repo, d, "目的 OK", flag)
    assert r.returncode != 0
    assert "--goal" in r.stdout + r.stderr
    assert state(d)["phase"] == "discovery" and "goal" not in state(d)


def test_approve_goal_is_refused_after_the_spec_is_building(repo):
    d = approved(repo)
    r = goal_approve(repo, d)
    assert r.returncode != 0
    assert "phase=building" in r.stdout + r.stderr
    assert "goal" not in state(d)


def test_goal_spec_is_not_dispatched_and_the_stop_hook_releases_it(repo):
    """目的として承認しても、実装役の dispatch と自走（building）には入らない。"""
    d = large_goal(repo)
    assert goal_approve(repo, d).returncode == 0
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(OVERNIGHT), "dispatch", str(d), "--task", "T1"], cwd=repo, capture_output=True, text=True,
                       env={**__import__("os").environ, "CLAUDE_CODE_SESSION_ID": "s1"}, timeout=60)
    assert r.returncode != 0
    assert "phase=discovery" in r.stdout + r.stderr
    assert "decision" not in json.loads(stop_hook(repo).stdout or "{}")


def test_record_keeps_what_another_process_wrote_after_the_caller_read_the_state(repo):
    """記録は書く直前に state.json を読み直し、goal のキーだけを足す（読み込み時の値を丸ごと書き戻さない）。"""
    d = init_spec(repo)
    stale = state(d)
    other = {**stale, "wait": {"reason": "別のプロセスが書いた", "at": 1.0}}
    (d / "state.json").write_text(json.dumps(other), encoding="utf-8")
    goal.record(d, "目的 OK", "a" * 64)
    s = state(d)
    assert s["wait"]["reason"] == "別のプロセスが書いた"
    assert s["goal"]["by"] == "目的 OK" and s["goal"]["scope_sha256"] == "a" * 64
