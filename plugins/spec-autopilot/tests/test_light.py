"""scripts/light.py（人との spec 合意を省く軽量フロー）を、入口から通して確かめる。

止まる条件（保護された path に触れたら check が通らない）と、自走の上限（PR 作成まで。マージ・QA の書き込みを受けない）を見る。
"""
import os
import subprocess
import sys
from pathlib import Path

from test_autopilot import GOOD_SPEC, PLUGIN, init_spec, make_done, repo, run, state, user_says  # noqa: F401（repo は fixture）

LIGHT = PLUGIN / "scripts" / "light.py"
NIGHT = PLUGIN / "scripts" / "overnight.py"


def light(cwd, *args):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(LIGHT), *args], cwd=cwd, capture_output=True, text=True, env=env)


def night(cwd, *args):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(NIGHT), *args], cwd=cwd, capture_output=True, text=True, env=env)


def light_approved(repo):
    d = init_spec(repo)
    r = light(repo, "approve", str(d), "--source", "Issue #1 の受入条件")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def test_approve_needs_no_human_reply_and_marks_the_run_light(repo):
    d = light_approved(repo)
    s = state(d)
    assert s["phase"] == "building" and s["light"] is True
    assert "人の承認なし" in s["approved_by"]


def test_approve_refuses_a_scope_wider_than_pr(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- 範囲: PR まで", "- 範囲: マージまで"), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "依頼文")
    assert r.returncode != 0
    assert state(d)["phase"] == "discovery"


def test_check_passes_when_no_protected_path_is_touched(repo):
    d = light_approved(repo)
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_stops_on_a_default_protected_path(repo):
    d = light_approved(repo)
    (repo / "terraform").mkdir()
    (repo / "terraform" / "main.tf").write_text("# x\n", encoding="utf-8")
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode != 0
    assert "terraform/main.tf" in r.stdout


def test_check_stops_on_an_uncommitted_agent_rule_file(repo):
    d = light_approved(repo)
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode != 0
    assert "CLAUDE.md" in r.stdout


def test_repo_config_adds_protected_paths(repo):
    d = light_approved(repo)
    (repo / ".spec-autopilot").mkdir()
    (repo / ".spec-autopilot" / "protected-paths").write_text("# 足す\nsecrets/*\n", encoding="utf-8")
    (repo / "secrets").mkdir()
    (repo / "secrets" / "a.txt").write_text("x\n", encoding="utf-8")
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode != 0
    assert "secrets/a.txt" in r.stdout


def test_protected_paths_do_not_stop_an_agreed_run(repo):
    d = init_spec(repo)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout + r.stderr


def test_human_approval_after_a_light_run_clears_the_light_mark(repo):
    d = light_approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "保護 path", "--evidence", "CLAUDE.md").returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    assert not state(d).get("light")


def test_light_run_refuses_merge_and_qa_records(repo):
    d = light_approved(repo)
    for args in (("ready", str(d), "--pr", "1"), ("merged", str(d), "--pr", "1"),
                 ("qa", str(d), "--evidence", str(d / "spec.md"))):
        r = night(repo, *args)
        assert r.returncode != 0, args
        assert "PR 作成まで" in r.stdout + r.stderr, args


def test_done_reports_the_pr_ceiling(repo):
    d = light_approved(repo)
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PR 作成まで" in r.stdout
