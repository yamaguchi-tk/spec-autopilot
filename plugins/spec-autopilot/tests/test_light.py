"""scripts/light.py（人との spec 合意を省く軽量フロー）を、入口から通して確かめる。

止まる条件（保護された path に触れたら check が通らない）と、自走の上限（PR 作成まで。マージ・QA の書き込みを受けない）を見る。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_autopilot import GOOD_SPEC, PLUGIN, existing_spec, init_spec, write_files, make_done, repo, run, state, user_says  # noqa: F401（repo は fixture）

LIGHT = PLUGIN / "scripts" / "light.py"
NIGHT = PLUGIN / "scripts" / "overnight.py"


def light(cwd, *args):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(LIGHT), *args], cwd=cwd, capture_output=True, text=True, env=env)


def night(cwd, *args):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(NIGHT), *args], cwd=cwd, capture_output=True, text=True, env=env)


def add(repo, *paths):
    subprocess.run(["git", "add", "--", *paths], cwd=repo, check=True)


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
    add(repo, "terraform/main.tf")
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode != 0
    assert "terraform/main.tf" in r.stdout


def test_check_stops_on_a_staged_agent_rule_file(repo):
    d = light_approved(repo)
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    add(repo, "CLAUDE.md")
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode != 0
    assert "CLAUDE.md" in r.stdout




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
    add(repo, "CLAUDE.md")
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


# --- 既存の repo（init の前に commit がある）---

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


def touch(repo, path, text="x\n"):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")
    add(repo, path)


def test_repo_config_at_the_start_adds_protected_paths(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "# 足す\nsecrets/*\n"})
    touch(repo, "secrets/a.txt")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "secrets/a.txt" in r.stdout


def test_a_committed_protected_change_stops(repo):
    d = committed_light(repo)
    touch(repo, "CLAUDE.md")
    commit_all(repo, "rules")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_an_uncommitted_change_to_a_tracked_protected_file_stops(repo):
    d = committed_light(repo, {"CLAUDE.md": "# rules\n"})
    (repo / "CLAUDE.md").write_text("# changed\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_renaming_a_protected_file_stops(repo):
    d = committed_light(repo, {"CLAUDE.md": "# rules\n"})
    subprocess.run(["git", "mv", "CLAUDE.md", "notes.md"], cwd=repo, check=True)
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_non_ascii_name_under_a_protected_dir_stops(repo):
    d = committed_light(repo)
    touch(repo, ".claude/commands/日本語.md")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "日本語.md" in r.stdout


def test_loosening_the_config_stops_on_the_config_itself(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "secrets/*\n"})
    (repo / ".spec-autopilot" / "protected-paths").write_text("", encoding="utf-8")
    touch(repo, "secrets/a.txt")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and ".spec-autopilot/protected-paths" in r.stdout and "secrets/a.txt" in r.stdout


@pytest.mark.parametrize("pat,path", [
    ("secrets/", "secrets/a.txt"), ("/secrets", "secrets/a.txt"), ("secrets", "x/secrets/a.txt"),
    ("*.sql", "db/m/001.sql"), ("config/prod", "config/prod/a.yml"), ("**/secrets", "a/b/secrets/c.txt"),
    ("**/migrations/*.sql", "services/a/migrations/001.sql"),
    ("config/**/secrets", "config/secrets/a.txt"), ("config/**/secrets", "config/a/secrets/a.txt"),
    ("config/**/secrets", "config/a/b/secrets/a.txt")])
def test_config_patterns_protect(repo, pat, path):
    """`/` を含まない行はどの深さにも、含む行は repo の root から当て、どちらも配下のファイルに当たる。照合は git の glob。"""
    d = committed_light(repo, {".spec-autopilot/protected-paths": pat + "\n"})
    touch(repo, path)
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and path in r.stdout


def test_a_rooted_pattern_does_not_match_deeper(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "config/prod\n"})
    touch(repo, "x/config/prod/a.yml")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_rework_after_done_stays_light(repo):
    d = committed_light(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "直して").returncode == 0
    assert state(d).get("light") is True
    touch(repo, "CLAUDE.md")
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


def test_approve_refuses_a_protected_file_committed_since_init(repo):
    """init から approve までの commit（S の試作）が保護 path に当たっていれば、軽量フローでは始めない。"""
    d = existing_spec(repo)
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", "docs/guardrails.md": "# 境界\n"})
    commit_all(repo, "prototype")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "docs/guardrails.md" in r.stdout + r.stderr
    assert state(d)["phase"] == "discovery"


def test_ignored_files_are_not_looked_at(repo):
    """git が無視するファイルは PR に入らないので判定しない（限界。commands/autopilot.md の L の 5）。"""
    d = committed_light(repo, {".gitignore": ".claude/\n"}, after_init={".claude/settings.local.json": "{}\n"})
    make_done(repo, d)
    (repo / ".claude" / "settings.local.json").write_text('{"x": 1}\n', encoding="utf-8")
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_an_untracked_protected_file_stops(repo):
    """追っていないファイルも、後で commit すれば PR に入るので止める。"""
    d = committed_light(repo)
    make_done(repo, d)
    write_files(repo, {"CLAUDE.md": "# rules\n", "terraform.tfstate": "{}\n"})
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout and "terraform.tfstate" in r.stdout


def test_a_protected_change_reverted_by_a_later_commit_is_not_counted(repo):
    """途中の commit で触れて後で戻したものは、PR が持ち込む差に入らないので数えない（限界）。"""
    d = committed_light(repo)
    touch(repo, "CLAUDE.md")
    commit_all(repo, "rules")
    (repo / "CLAUDE.md").unlink()
    commit_all(repo, "revert")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_approve_prints_the_ceiling_once(repo):
    d = light_approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0 and "PR 作成まで" in r.stdout and "NOTE: NOTE:" not in r.stdout


def test_the_specs_own_directory_is_not_a_protected_path(repo):
    """slug が保護の pattern（*guardrails*）に当たっても、spec 自身の置き場では止めない（置き場を追う repo でも）。"""
    d = init_spec(repo, "guardrails-wording")
    add(repo, str(d.relative_to(repo)))
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    add(repo, str(d.relative_to(repo)))
    r = check_pr(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr


def test_an_adr_matching_a_protected_pattern_is_counted(repo):
    """ADR は保護から除かない。ADR の名前が *guardrails* に当たると approve が断る（止める側）。"""
    d = existing_spec(repo, files={"docs/adr/README.md": "# ADR\n"})
    adr = "docs/adr/2026-01-01-guardrails-wording.md"
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n", adr: "# ADR\n"})
    add(repo, adr)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("docs/adr/2026-01-01-game.md", adr), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and adr in out and "保護された path に承認の前から当たっている" in out


def test_core_ignorecase_matches_any_case(repo):
    subprocess.run(["git", "config", "core.ignorecase", "true"], cwd=repo, check=True)
    d = committed_light(repo)
    touch(repo, "Claude.md")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "Claude.md" in r.stdout


def test_a_committed_change_restored_only_in_the_worktree_stops(repo):
    """PR に入るのは HEAD。commit した保護 path を作業ツリーだけ戻しても止める。"""
    d = committed_light(repo, {"CLAUDE.md": "# rules\n"})
    (repo / "CLAUDE.md").write_text("# changed\n", encoding="utf-8")
    commit_all(repo, "rules")
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_a_staged_file_removed_from_the_worktree_stops(repo):
    d = committed_light(repo)
    make_done(repo, d)
    touch(repo, ".mcp.json", "{}\n")
    (repo / ".mcp.json").unlink()
    r = check_pr(repo, d)
    assert r.returncode != 0 and ".mcp.json" in r.stdout


def test_literal_pathspecs_in_the_environment_do_not_disable_matching(repo):
    d = committed_light(repo)
    make_done(repo, d)
    touch(repo, "CLAUDE.md")
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "autopilot.py"), "check", str(d), "--stage", "pr"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_any_case_matches_without_core_ignorecase(repo):
    subprocess.run(["git", "config", "core.ignorecase", "false"], cwd=repo, check=True)
    d = committed_light(repo)
    touch(repo, "Claude.md")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "Claude.md" in r.stdout


def test_an_unreadable_start_stops(repo):
    """起点を読めないときは、判定できないので止める（通さない）。"""
    import json
    d = light_approved(repo)
    make_done(repo, d)
    s = json.loads((d / "state.json").read_text(encoding="utf-8"))
    s["light_base"] = "0" * 40
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    r = check_pr(repo, d)
    assert r.returncode != 0 and "確かめられない" in r.stdout
