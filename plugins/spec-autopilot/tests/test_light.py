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
                 ("qa", str(d), "--evidence", str(d / "spec.md"), "--smoke", "pass")):
        r = night(repo, *args)
        assert r.returncode != 0, args
        assert "PR 作成まで" in r.stdout + r.stderr, args


def test_done_reports_the_pr_ceiling(repo):
    d = light_approved(repo)
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PR 作成まで" in r.stdout


# --- 1 巡目のレビューの指摘（commit のある repo で承認する） ---

def commit_all(repo, msg="c"):
    subprocess.run(["git", "add", "-A", "--", ".", ":(exclude)docs/specs"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                    "commit", "-qm", msg], cwd=repo, check=True)


def committed_light(repo, files=None):
    for name, body in {"src.js": "// x\n", **(files or {})}.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(body, encoding="utf-8")
    commit_all(repo, "init")
    return light_approved(repo)


def check_pr(repo, d):
    return run(repo, "check", str(d), "--stage", "pr")


def test_renaming_a_protected_file_stops(repo):
    d = committed_light(repo, {"CLAUDE.md": "# rules\n"})
    subprocess.run(["git", "mv", "CLAUDE.md", "notes.md"], cwd=repo, check=True)
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_non_ascii_name_under_a_protected_dir_stops(repo):
    d = committed_light(repo)
    (repo / ".claude" / "commands").mkdir(parents=True)
    (repo / ".claude" / "commands" / "日本語.md").write_text("x\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "日本語.md" in r.stdout


def test_loosening_the_config_after_approval_does_not_unprotect(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "secrets/*\n"})
    (repo / ".spec-autopilot" / "protected-paths").write_text("", encoding="utf-8")
    (repo / "secrets").mkdir()
    (repo / "secrets" / "a.txt").write_text("x\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "secrets/a.txt" in r.stdout


def test_gitignore_style_directory_patterns_protect(repo):
    for i, pat in enumerate(("secrets/", "/secrets", "config/prod")):
        sub = repo / f"r{i}"
        sub.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=sub, check=True)
        d = committed_light(sub, {".spec-autopilot/protected-paths": pat + "\n"})
        target = sub / ("config/prod/a.yml" if "config" in pat else "secrets/a.txt")
        target.parent.mkdir(parents=True)
        target.write_text("x\n", encoding="utf-8")
        make_done(sub, d)
        r = check_pr(sub, d)
        assert r.returncode != 0, pat


def test_rework_after_done_stays_light(repo):
    d = committed_light(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "直して").returncode == 0
    assert state(d).get("light") is True


def test_light_approve_refuses_a_dependent_spec(repo):
    d = init_spec(repo)
    text = (d / "spec.md").read_text(encoding="utf-8").replace("- 予算: 30 分", "- 予算: 30 分\n- 依る spec: other")
    (d / "spec.md").write_text(text, encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "依頼文")
    assert r.returncode != 0 and state(d)["phase"] == "discovery"


def test_light_approve_refuses_a_size_above_s(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- 大きさ: S", "- 大きさ: M"), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "依頼文")
    assert r.returncode != 0 and state(d)["phase"] == "discovery"


def test_runlog_marks_light_runs(repo):
    import json
    d = light_approved(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    rows = (Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(rows[-1])["light"] is True


def test_light_run_refuses_rolled_back(repo):
    d = light_approved(repo)
    r = night(repo, "rolled-back", str(d), "--evidence", str(d / "spec.md"), "--reason", "x")
    assert r.returncode != 0 and "PR 作成まで" in r.stdout + r.stderr
