"""scripts/light.py（人との spec 合意を省く軽量フロー）を、入口から通して確かめる。

止まる条件（保護された path に触れたら check が通らない）と、自走の範囲が合意ありと同じく spec の `- 範囲:` で決まることを見る。
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
    """PR に入るのは HEAD。commit した保護 path を作業ツリーと index だけ戻しても止める。"""
    d = committed_light(repo, {"CLAUDE.md": "# rules\n"})
    (repo / "CLAUDE.md").write_text("# changed\n", encoding="utf-8")
    commit_all(repo, "rules")
    make_done(repo, d)
    (repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    add(repo, "CLAUDE.md")  # index も起点と同じにする（HEAD だけが違う）
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


def test_a_config_whose_blob_is_missing_stops(repo):
    """起点の木に設定があって中身を読めないときは、足した pattern を落とさずに止める。"""
    d = committed_light(repo, {".spec-autopilot/protected-paths": "secrets\n"})
    make_done(repo, d)
    oid = subprocess.run(["git", "rev-parse", f"{state(d)['light_base']}:.spec-autopilot/protected-paths"], cwd=repo,
                         capture_output=True, text=True, check=True).stdout.strip()
    (repo / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
    r = check_pr(repo, d)
    assert r.returncode != 0 and "確かめられない" in r.stdout


@pytest.mark.parametrize("link", [".spec-autopilot/protected-paths", ".spec-autopilot"])
def test_a_symlinked_config_stops(repo, link):
    """設定かその置き場が symlink のときは中身を読めないので止める（リンク先の pattern を黙って落とさない）。"""
    (repo / "conf").mkdir()
    (repo / "conf" / "protected-paths").write_text("secrets\n", encoding="utf-8")
    if link == ".spec-autopilot":
        os.symlink("conf", repo / ".spec-autopilot")
    else:
        (repo / ".spec-autopilot").mkdir()
        os.symlink("../conf/protected-paths", repo / link)
    d = existing_spec(repo, files={"README.md": "# x\n"})
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and f"普通のファイルでない: {link}（120000）" in r.stdout + r.stderr


def test_a_config_with_a_bom_is_read(repo):
    d = committed_light(repo, {".spec-autopilot/protected-paths": "\ufeffsecrets\n"})
    touch(repo, "secrets/a.txt")
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "secrets/a.txt" in r.stdout


@pytest.mark.parametrize("text", ["\u200bsecrets\n", "secr\u200bets\n", b"secrets\xff\n"])
def test_a_config_with_unreadable_characters_stops(repo, text):
    """見えない文字や UTF-8 でない中身は、足した pattern が黙って効かなくなるので止める。"""
    f = repo / ".spec-autopilot" / "protected-paths"
    f.parent.mkdir()
    f.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    d = existing_spec(repo, files={"README.md": "# x\n"})  # init の前の commit に設定も入る（git add -A）
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "確かめられない" in r.stdout + r.stderr


def test_light_run_follows_the_specs_scope_up_to_merge_and_qa(repo, scope="マージまで"):
    """軽量フローも、合意ありと同じく spec の範囲までマージ・QA に進む（記録のコマンドを断らない）。"""
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- 範囲: PR まで", f"- 範囲: {scope}"), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "Issue #1 の受入条件")
    assert r.returncode == 0, r.stdout + r.stderr
    for args in (("ready", str(d), "--pr", "1"), ("merged", str(d), "--pr", "1"),
                 ("qa", str(d), "--evidence", str(d / "spec.md"), "--smoke", "pass")):
        out = night(repo, *args)
        assert "軽量フロー" not in out.stdout + out.stderr, args


@pytest.mark.parametrize("row", [{"デプロイの起動": "コマンド: make deploy"}, {"ロールバック": "コマンド: make rollback"}])
def test_approve_refuses_deploy_or_rollback_commands_nobody_has_seen(repo, row):
    """軽量フローでは人が spec を見ないので、agent が書いたコマンドを打つ範囲では始めない。"""
    from test_overnight import FULL, deployed, scoped
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **row)), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and f"ERROR: 軽量フローでは `- {next(iter(row))}:`" in r.stdout
    assert state(d)["phase"] == "discovery"


@pytest.mark.parametrize("key", ["デプロイの起動", "ロールバック"])
def test_a_command_written_before_a_reapproval_still_stops_check(repo, key):
    """block の後の返事は spec の全体を見たものではないので、再承認の後もコマンドは打たせない。"""
    d = light_approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "x").returncode == 0
    from test_overnight import scoped
    (d / "spec.md").write_text(scoped("マージまで", **{key: "コマンド: make x"}), encoding="utf-8")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    make_done(repo, d)
    r = check_pr(repo, d)
    assert r.returncode != 0 and f"ERROR: 軽量フローでは `- {key}:`" in r.stdout and "autopilot.py block" in r.stdout


@pytest.mark.parametrize("row", ["- デプロイの起動: コマンド: make deploy", "- ロールバック：コマンド：make rollback"])
def test_approve_refuses_a_command_in_a_second_scope_section(repo, row):
    """節が 2 つあっても、どちらかにコマンドがあれば断る（読み手が最初の節だけを見る抜けを作らない）。"""
    from test_overnight import scoped
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped("マージまで") + f"\n## 自走の範囲\n{row}\n", encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "ERROR: 軽量フローでは" in r.stdout, r.stdout


@pytest.mark.parametrize("how", ["unclosed-comment", "fullwidth-comment", "indented", "bold", "table"])
def test_approve_refuses_a_command_in_any_shape_the_agent_may_read(repo, how):
    """コメントの外し方や行の形で、使う側に見えるコマンドを見落とさない（鍵の語と `コマンド:` が同じ行にあれば断る）。"""
    from test_overnight import scoped
    base = scoped("マージまで")
    row = "- ロールバック: コマンド: make rollback"
    text = {
        "unclosed-comment": base.replace("- ロールバック: revert の PR をマージし、デプロイの完了を確かめる",
                                         "<!-- メモ\n" + row).replace("## 止まる条件", "<!-- x -->\n## 止まる条件"),
        "fullwidth-comment": base.replace("- ロールバック: revert の PR をマージし、デプロイの完了を確かめる", "＜！－－\n" + row + "\n-->"),
        "indented": base + "\n  - デプロイの起動: コマンド: make deploy\n",
        "bold": base + "\n* **デプロイの起動**: コマンド: make deploy\n",
        "table": base + "\n| ロールバック | コマンド: make rollback |\n",
    }[how]
    d = init_spec(repo)
    (d / "spec.md").write_text(text, encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "ERROR: 軽量フローでは" in r.stdout, r.stdout


def test_approve_takes_the_full_scope_when_merge_deploys_by_itself(repo):
    from test_overnight import FULL, deployed, scoped
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL)), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_rule_file_inside_the_spec_directory_stops(repo):
    """spec の置き場は、置き場の名前では当てないが、置き場の下の保護名には当てる。"""
    d = init_spec(repo, "guardrails-wording")
    assert light(repo, "approve", str(d), "--source", "x").returncode == 0
    make_done(repo, d)
    (d / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    add(repo, str(d.relative_to(repo)))
    r = check_pr(repo, d)
    assert r.returncode != 0 and "CLAUDE.md" in r.stdout


def test_a_submodule_pointer_under_a_protected_path_stops_even_if_ignored(repo):
    """.gitmodules の ignore=all や diff.ignoreSubmodules があっても、gitlink の変更は数える。"""
    d = committed_light(repo)
    make_done(repo, d)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", f"160000,{head},terraform"], cwd=repo, check=True)
    subprocess.run(["git", "config", "diff.ignoreSubmodules", "all"], cwd=repo, check=True)
    r = check_pr(repo, d)
    assert r.returncode != 0 and "terraform" in r.stdout
