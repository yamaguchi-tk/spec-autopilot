"""scripts/light.py（人との spec 合意を省く軽量フロー）を、入口から通して確かめる。

止まる条件（保護された path に触れたら check が通らない）と、自走の上限（PR 作成まで。マージ・QA の書き込みを受けない）を見る。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from test_autopilot import GOOD_SPEC, PLUGIN, existing_spec, init_spec, write_files, make_done, repo, run, state, user_says  # noqa: F401（repo は fixture）

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


def test_human_approval_after_a_light_block_keeps_the_light_mark(repo):
    """block の後の返事は spec の全体を見たものではないので、印は外さない（合意ありにするなら spec を作り直す）。"""
    d = light_approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "保護 path", "--evidence", "CLAUDE.md").returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    assert state(d).get("light") is True
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


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


def committed_light(repo, files=None, after_init=None):
    """既存の repo（files を init の前に commit）で spec を作り、S の試作（src/board.js）と after_init を書いてから軽量フローで承認する。"""
    d = existing_spec(repo, files=files)
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", **(after_init or {})})
    r = light(repo, "approve", str(d), "--source", "Issue #1 の受入条件")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


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
    for i, pat in enumerate(("secrets/", "/secrets", "config/prod", "**/secrets")):
        sub = repo / f"r{i}"
        sub.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=sub, check=True)
        d = committed_light(sub, {".spec-autopilot/protected-paths": pat + "\n"})
        target = sub / ("config/prod/a.yml" if "config" in pat else "secrets/a.txt")
        target.parent.mkdir(parents=True)
        target.write_text("x\n", encoding="utf-8")
        make_done(sub, d)
        r = check_pr(sub, d)
        assert r.returncode != 0 and target.relative_to(sub).as_posix() in r.stdout, pat


def test_rework_after_done_stays_light(repo):
    d = committed_light(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "直して").returncode == 0
    assert state(d).get("light") is True
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


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


# --- 2 巡目のレビューの指摘 ---

def test_approve_refuses_a_protected_file_committed_since_init(repo):
    """init から approve までの commit（S の試作）が保護 path に当たっていれば、軽量フローでは始めない。"""
    d = existing_spec(repo)
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", "docs/guardrails.md": "# 境界\n"})
    commit_all(repo, "prototype")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "docs/guardrails.md" in r.stdout + r.stderr
    assert state(d)["phase"] == "discovery"


def test_approve_refuses_an_untracked_protected_file(repo):
    d = existing_spec(repo)
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", "docs/guardrails.md": "# 境界\n"})
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "docs/guardrails.md" in r.stdout + r.stderr


def test_reverting_a_committed_protected_change_only_in_the_worktree_still_stops(repo):
    d = committed_light(repo)
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    commit_all(repo, "rules")
    (repo / "CLAUDE.md").unlink()
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


IGNORED = {".gitignore": ".claude/\n"}


def test_ignored_protected_files_are_not_looked_at(repo):
    """git が無視するファイルは PR に入らないので判定しない（限界。commands/autopilot.md の L の 5）。"""
    d = committed_light(repo, IGNORED, after_init={".claude/settings.local.json": "{}\n"})
    (repo / ".claude" / "settings.local.json").write_text('{"x": 1}\n', encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_protected_change_left_only_in_head_stops(repo):
    """commit した後に index と作業ツリーから消しても、HEAD に残るなら PR に入るので止める。"""
    d = committed_light(repo)
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    commit_all(repo, "rules")
    subprocess.run(["git", "rm", "-q", "CLAUDE.md"], cwd=repo, check=True)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_a_protected_change_reverted_by_a_later_commit_stops(repo):
    d = committed_light(repo)
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    commit_all(repo, "rules")
    (repo / "CLAUDE.md").unlink()
    commit_all(repo, "revert")
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_approve_prints_the_ceiling_once(repo):
    d = light_approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0 and "PR 作成まで" in r.stdout and "NOTE: NOTE:" not in r.stdout


def test_approve_refuses_an_uncommitted_config(repo):
    """commit していない設定（それ自身が保護 path）は、承認の時点の版を残せないので、軽量フローでは始めない。"""
    d = init_spec(repo)
    (repo / ".spec-autopilot").mkdir()
    (repo / ".spec-autopilot" / "protected-paths").write_text("secrets\n", encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and ".spec-autopilot/protected-paths" in r.stdout + r.stderr


def test_the_specs_own_directory_is_not_a_protected_path(repo):
    """slug が保護の pattern（*guardrails*）に当たっても、spec 自身の置き場では止めない。"""
    d = init_spec(repo, "guardrails-wording")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


# --- 6 巡目のレビューの指摘 ---

def git_c(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
                   cwd=repo, check=True, capture_output=True)


def merge_side(repo, change):
    git_c(repo, "checkout", "-q", "-b", f"side{time.time_ns()}")
    git_c(repo, "commit", "-q", "--allow-empty", "-m", "side")
    git_c(repo, "checkout", "-q", "-")
    git_c(repo, "merge", "-q", "--no-commit", "--no-ff", "-")
    change()
    git_c(repo, "commit", "-q", "-m", "merge")


def test_a_protected_change_only_inside_merge_commits_stops(repo):
    """merge の commit の中だけで足し、別の merge の中で消した保護 path も数える。"""
    d = committed_light(repo)
    make_done(repo, d)
    merge_side(repo, lambda: ((repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8"), git_c(repo, "add", "CLAUDE.md")))
    merge_side(repo, lambda: git_c(repo, "rm", "-q", "CLAUDE.md"))
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_an_adr_matching_a_protected_pattern_is_counted(repo):
    """ADR は保護から除かない。ADR の名前が *guardrails* に当たると approve が断る（止める側）。"""
    d = existing_spec(repo, files={"docs/adr/README.md": "# ADR\n"})
    adr = "docs/adr/2026-01-01-guardrails-wording.md"
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", adr: "# ADR\n"})
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("docs/adr/2026-01-01-game.md", adr), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and adr in out and "保護された path に承認の前から当たっている" in out


def test_an_untracked_tfstate_stops(repo):
    d = committed_light(repo)
    make_done(repo, d)
    (repo / "terraform.tfstate").write_text("{}\n", encoding="utf-8")
    r = check_pr(repo, d)
    assert r.returncode != 0 and "terraform.tfstate" in r.stdout


def test_a_rule_file_inside_the_spec_directory_stops(repo):
    d = committed_light(repo, {"docs/specs/README.md": "# specs\n"})  # spec を commit する repo（init が置き場を無視にしない）
    make_done(repo, d)
    (d / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_a_double_star_pattern_with_a_slash_protects_at_any_depth(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "**/migrations/*.sql\n"})
    make_done(repo, d)
    (repo / "services" / "a" / "migrations").mkdir(parents=True)
    (repo / "services" / "a" / "migrations" / "001.sql").write_text("x\n", encoding="utf-8")
    r = check_pr(repo, d)
    assert r.returncode != 0 and "services/a/migrations/001.sql" in r.stdout
