"""hooks/agent_gate.py（実装役の起動の入口で、開いた dispatch の無い起動を deny する PreToolUse hook）を、
payload を stdin で渡す入口と、hooks.json の command（答えを出さずに終わったときの deny）から確かめる。"""
import json
import os
import shutil
import stat
import subprocess
import sys
import time

import pytest

from test_autopilot import PLUGIN, hand_off, implementer_ran, init_spec, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_overnight import full_spec, gh, git_head, merged_pr, night  # noqa: F401（gh は fixture）

GATE = PLUGIN / "hooks" / "agent_gate.py"
IMPL = "spec-autopilot:autopilot-implementer"
REVIEWER = "spec-autopilot:autopilot-reviewer"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def fire(cwd, prompt, agent=IMPL, tool="Agent", stdin=None):
    payload = stdin if stdin is not None else json.dumps(
        {"tool_name": tool, "tool_input": {"subagent_type": agent, "prompt": prompt}, "cwd": str(cwd)})
    return subprocess.run([sys.executable, str(GATE)], input=payload, capture_output=True, text=True, timeout=30)


def decision(r):
    assert r.returncode == 0, r.stdout + r.stderr
    if not r.stdout.strip():
        return None
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    return out["permissionDecision"], out["permissionDecisionReason"]


def denial(r):
    """deny の (kind, 理由)。deny が外れて何も出ないときは、タプルの展開の TypeError でなく assert で落とす。"""
    got = decision(r)
    assert got is not None and got[0] == "deny", got
    return got


def building(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("# タスク\n\n- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    assert state(d)["phase"] == "building"
    return d


def dispatched(repo, d):
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def test_gate_denies_an_implementer_when_no_dispatch_was_made(repo):
    d = building(repo)
    kind, why = decision(fire(repo, f"spec は {d} です。T1 を実装して"))
    assert kind == "deny" and "overnight.py dispatch" in why


def test_gate_allows_an_implementer_while_the_dispatch_is_open(repo):
    d = dispatched(repo, building(repo))
    assert decision(fire(repo, f"spec: {d}。T1")) is None


def test_gate_denies_after_the_dispatch_was_closed_by_a_handoff(repo):
    d = dispatched(repo, building(repo))
    st = state(d)
    st["handoffs"] = [{"tip": "x", "tasks": ["T1"], "dispatch": 0, "at": 1}]
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    kind, why = decision(fire(repo, f"{d}"))
    assert kind == "deny" and "overnight.py dispatch" in why


def test_gate_denies_an_implementer_of_another_rung(repo):
    d = dispatched(repo, building(repo))
    kind, _ = decision(fire(repo, f"{d}", agent="spec-autopilot:autopilot-implementer-fable"))
    assert kind == "deny"


def test_gate_allows_when_any_named_spec_has_an_open_dispatch(repo):
    d = dispatched(repo, building(repo))
    other = init_spec(repo, "other")
    assert decision(fire(repo, f"{other} と {d}")) is None


def test_gate_resolves_a_relative_spec_path_from_the_payload_cwd(repo):
    d = dispatched(repo, building(repo))
    assert decision(fire(repo, str(d.relative_to(repo)))) is None
    assert decision(fire(repo, str(d.relative_to(repo)) + "/", agent="autopilot-implementer")) is None


def test_gate_denies_when_the_prompt_names_no_spec_directory(repo):
    building(repo)
    kind, why = decision(fire(repo, "T1 を実装して"))
    assert kind == "deny" and "spec" in why


def test_gate_denies_when_state_json_is_broken(repo):
    d = dispatched(repo, building(repo))
    (d / "state.json").write_text("{broken", encoding="utf-8")
    kind, why = decision(fire(repo, f"{d}"))
    assert kind == "deny" and "state.json" in why


def test_gate_denies_when_the_payload_is_not_json(repo):
    kind, why = decision(fire(repo, "", stdin="not json"))
    assert kind == "deny" and why


def test_gate_stays_silent_for_an_agent_that_is_not_an_implementer(repo):
    d = building(repo)
    (d / "state.json").write_text("{broken", encoding="utf-8")  # 読めば deny になる状態でも、読まない
    assert decision(fire(repo, f"{d}", agent="spec-autopilot:autopilot-reviewer")) is None
    assert decision(fire(repo, "x", agent="general-purpose")) is None


def closed(repo):
    """最後の dispatch を今の HEAD の handoff で閉じた building の spec（review を記録できる状態）。"""
    d = building(repo)
    (d / "tasks.md").write_text("# タスク\n\n- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")  # handoff は終えたタスクだけ閉じる
    hand_off(repo, d)
    return d


def test_gate_records_a_reviewer_launch_in_the_building_spec_and_allows_it(repo):
    d = closed(repo)
    assert not state(d).get("review_launches")
    before = time.time()
    assert decision(fire(repo, f"spec: {d}。base..tip を評価して", agent=REVIEWER)) is None
    launches = state(d)["review_launches"]
    assert len(launches) == 1 and launches[0] >= before
    assert decision(fire(repo, f"spec: {d}", agent="autopilot-reviewer-fable")) is None
    assert len(state(d)["review_launches"]) == 2
    assert decision(fire(repo, f"spec は {d.relative_to(repo)} です", agent=REVIEWER, tool="Task")) is None
    assert len(state(d)["review_launches"]) == 3


def test_gate_leaves_state_alone_when_the_reviewer_names_no_building_spec(repo):
    d = building(repo)
    other = init_spec(repo, "draft")  # discovery
    before = {p: (p / "state.json").read_bytes() for p in (d, other)}
    assert decision(fire(repo, "評価して", agent=REVIEWER)) is None
    assert decision(fire(repo, f"spec: {other}", agent=REVIEWER)) is None
    broken = init_spec(repo, "broken")
    (broken / "state.json").write_text("{not json", encoding="utf-8")
    before[broken] = (broken / "state.json").read_bytes()
    assert decision(fire(repo, f"spec: {broken} と docs/specs/2026-11-27-missing", agent=REVIEWER)) is None
    assert {p: (p / "state.json").read_bytes() for p in (d, other, broken)} == before


def test_gate_denies_an_implementer_while_a_reviewer_result_is_not_recorded(repo):
    d = building(repo)
    (d / "tasks.md").write_text("# タスク\n\n- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    hand_off(repo, d)
    assert decision(fire(repo, f"{d}", agent=REVIEWER)) is None
    assert len(state(d)["review_launches"]) == 1
    s = state(d)
    s["dispatches"].append({**s["dispatches"][-1], "at": time.time()})  # 直しの dispatch を開く
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    kind, why = decision(fire(repo, f"{d}"))
    assert kind == "deny" and "autopilot.py review" in why and str(d) in why


def test_reviewer_launch_while_a_dispatch_is_open_is_denied_and_records_nothing(repo):
    d = dispatched(repo, building(repo))
    before = (d / "state.json").read_bytes()
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert kind == "deny" and "最後の dispatch" in why and "overnight.py handoff" in why and str(d) in why
    assert "実装役を起動できない" not in why and "overnight.py dispatch" not in why
    assert (d / "state.json").read_bytes() == before
    assert decision(fire(repo, f"{d}")) is None


def test_reviewer_launch_in_a_spec_without_dispatch_is_denied_and_dispatch_still_opens(repo):
    d = building(repo)  # 承認の直後（dispatch が 1 つも無い）。review は「handoff が閉じていない」で断る
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert kind == "deny" and "handoff が閉じていない" in why and "overnight.py handoff" in why
    assert not state(d).get("review_launches")
    dispatched(repo, d)
    assert decision(fire(repo, f"{d}")) is None


def test_reviewer_launch_with_uncommitted_code_is_denied_with_the_review_gate_sentence(repo):
    d = closed(repo)
    (repo / "uncommitted.py").write_text("x = 1\n", encoding="utf-8")  # review は「commit していないコード」で断る
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert kind == "deny" and "commit していないコードがある: uncommitted.py" in why
    assert not state(d).get("review_launches")


def test_reviewer_prompt_naming_a_building_and_a_discovery_spec_records_only_the_building_one_and_passes(repo):
    gated = closed(repo)
    ungated = init_spec(repo, "ungated")  # discovery は building でないので数えない
    assert decision(fire(repo, f"{ungated} と {gated}", agent=REVIEWER)) is None
    assert len(state(gated)["review_launches"]) == 1 and not state(ungated).get("review_launches")


def test_reviewer_prompt_naming_a_receiving_and_a_refusing_building_spec_records_only_the_receiving_one(repo):
    receiving = closed(repo)
    other = repo / "docs" / "specs" / "2026-11-27-refusing"
    shutil.copytree(receiving, other)  # 同じ state.json の写し（handoff の記録が別の dispatch の番号を指さない）
    s = state(other)
    s["handoffs"] = []  # こちらは handoff が閉じていない
    (other / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert decision(fire(repo, f"{other} と {receiving}", agent=REVIEWER)) is None
    assert len(state(receiving)["review_launches"]) == 1 and not state(other).get("review_launches")
    kind, why = denial(fire(repo, f"{other}", agent=REVIEWER))
    assert kind == "deny" and str(other) in why


def test_reviewer_launch_denied_after_only_a_spec_file_commit_passes_after_the_handoff_is_redone(repo):
    d = closed(repo)
    (d / "qa.md").write_text("# qa\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "-f", "-A", "--", "docs/specs"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "spec のファイルだけ"], cwd=repo, check=True)
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert kind == "deny" and "overnight.py handoff" in why and not state(d).get("review_launches")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert decision(fire(repo, f"{d}", agent=REVIEWER)) is None
    assert len(state(d)["review_launches"]) == 1


def test_reviewer_launch_after_the_merge_commit_is_denied_and_passes_after_the_handoff_is_redone(repo, gh):
    """マージの記録がある building の spec（デプロイ後の QA の段）。checkout をマージの commit に置くと HEAD が動いて deny になる。"""
    d = closed(repo)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "Merge pull request #7"], cwd=repo, check=True)  # マージの commit
    assert state(d)["merges"]
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert kind == "deny" and "overnight.py handoff" in why and not state(d).get("review_launches")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert decision(fire(repo, f"{d}", agent=REVIEWER)) is None
    assert len(state(d)["review_launches"]) == 1


def test_reviewer_launch_with_a_broken_git_index_is_denied_with_the_directory_and_exception_type(repo):
    """handoff で閉じた後に .git/index を壊す（rev-parse HEAD は通り、git status が落ちて review_gate が RuntimeError を出す）。"""
    d = closed(repo)
    (repo / ".git" / "index").write_bytes(b"DIRC\x00\x00\x00\x02\x00\x00\x00\x01")
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True).returncode == 0
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True).returncode != 0
    before = (d / "state.json").read_bytes()
    kind, why = denial(fire(repo, f"{d}", agent=REVIEWER))
    assert str(d) in why and "RuntimeError" in why and "overnight.py handoff" in why
    assert (d / "state.json").read_bytes() == before


def test_reviewer_launch_with_an_unreadable_state_json_still_passes_and_records_nothing(repo):
    d = closed(repo)
    (d / "state.json").write_text("{not json", encoding="utf-8")
    r = fire(repo, f"{d}", agent=REVIEWER)
    assert decision(r) is None and (d / "state.json").read_text(encoding="utf-8") == "{not json"


def test_reviewer_launch_that_cannot_be_recorded_is_named_on_stderr_and_passes(repo):
    d = closed(repo)
    mode = d.stat().st_mode
    os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
    try:
        r = fire(repo, f"{d}", agent=REVIEWER)
    finally:
        os.chmod(d, mode)
    assert decision(r) is None
    assert "PermissionError" in r.stderr and str(d) in r.stderr and len(r.stderr.strip().splitlines()) == 1
    assert not state(d).get("review_launches")


def test_dispatch_refuses_until_the_reviewer_result_is_recorded(repo):
    d = building(repo)
    (d / "tasks.md").write_text("# タスク\n\n- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")  # handoff は終えたタスクだけ閉じる
    hand_off(repo, d)
    assert decision(fire(repo, f"{d}", agent=REVIEWER)) is None
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode != 0 and "autopilot.py review" in r.stdout + r.stderr
    assert run(repo, "review", str(d), "--high", "none").returncode == 0
    dispatched(repo, d)
    assert decision(fire(repo, f"{d}")) is None


def test_reapproval_moves_review_launches_to_history_and_starts_empty(repo):
    d = building(repo)
    st = state(d)
    st.update(phase="done", done_at=time.time(), review_launches=[time.time()])
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    s = state(d)
    assert s["phase"] == "building" and not s.get("review_launches")
    assert any(len(h.get("review_launches") or []) == 1 for h in s["history"]), s["history"]


def test_hooks_json_registers_the_gate_on_agent_and_task():
    pre = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    assert len(pre) == 1 and set(pre[0]["matcher"].split("|")) == {"Agent", "Task"}
    assert "agent_gate.py" in pre[0]["hooks"][0]["command"]


def hook_command(root):
    pre = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    return pre[0]["hooks"][0]["command"], {**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)}


def test_hook_command_denies_when_the_script_cannot_be_imported(tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "agent_gate.py").write_text("import no_such_module_xyz\n", encoding="utf-8")
    cmd, env = hook_command(root)
    r = subprocess.run(cmd, shell=True, input="{}", capture_output=True, text=True, env=env, timeout=30)
    assert decision(r)[0] == "deny"


def test_hook_command_denies_when_the_script_exits_nonzero(tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "agent_gate.py").write_text("import sys; print('partial'); sys.exit(3)\n", encoding="utf-8")
    cmd, env = hook_command(root)
    r = subprocess.run(cmd, shell=True, input="{}", capture_output=True, text=True, env=env, timeout=30)
    assert decision(r)[0] == "deny"


def test_hook_command_passes_the_real_script_answer_through(repo):
    d = dispatched(repo, building(repo))
    cmd, env = hook_command(PLUGIN)
    payload = json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": IMPL, "prompt": str(d)}, "cwd": str(repo)})
    r = subprocess.run(cmd, shell=True, input=payload, capture_output=True, text=True, env=env, timeout=30)
    assert decision(r) is None


@pytest.mark.parametrize("dirname", ["my repo", "日本語 の repo"])
def test_gate_allows_an_open_dispatch_under_a_path_with_spaces_or_japanese(tmp_path, monkeypatch, dirname):
    monkeypatch.setenv("SPEC_AUTOPILOT_HOME", str(tmp_path / ".autopilot-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude-config"))
    root = tmp_path / dirname
    root.mkdir()
    subprocess.run(GIT[:1] + ["init", "-q", str(root)], check=True)
    d = dispatched(root, building(root))
    assert " " in str(d)
    assert decision(fire(root, f"spec は {d} です。T1 を実装して")) is None
    assert decision(fire(root, f"spec: {d}/")) is None
    assert decision(fire(root, str(d.relative_to(root)))) is None


@pytest.mark.parametrize("prompt", [
    "{d}を実装して。T1",
    "{d}の T1 を実装して",
    "spec は「{d}」です。T1",
    "spec のディレクトリ：{d}",
    "spec（{d}）の T1",
    "spec は{d} の T1",
    "T1 を、{d} で",
    "T1。{d}。",
    "spec【{d}】",
    "spec={d}を",
    "{d}/を実装",
    "spec は『{d}』と〈{d}〉",
])
@pytest.mark.parametrize("dirname", ["plain", "my repo", "日本語 の repo"])
def test_gate_allows_an_open_dispatch_whose_path_touches_japanese_or_fullwidth_marks(tmp_path, monkeypatch, dirname, prompt):
    monkeypatch.setenv("SPEC_AUTOPILOT_HOME", str(tmp_path / ".autopilot-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude-config"))
    root = tmp_path / dirname
    root.mkdir()
    subprocess.run(GIT[:1] + ["init", "-q", str(root)], check=True)
    d = dispatched(root, building(root))
    assert decision(fire(root, prompt.format(d=d))) is None


def test_gate_stays_linear_on_long_lines_without_a_spec_in_them(repo):
    import time
    d = dispatched(repo, building(repo))
    words = " ".join(f"w{i}" for i in range(4000))[:4000]
    slashes = "../" * 1300
    ja = ("実装する、規則を守る。" * 400)[:4000]
    for line in (words, slashes, "/" * 4000, ja, "a/" * 2000):
        prompt = "\n".join([line] * 4) + f"\nspec: {d}"
        t = time.time()
        assert decision(fire(repo, prompt)) is None
        assert time.time() - t < 3, line[:20]


def test_gate_denies_quickly_on_a_long_line_without_any_spec(repo):
    import time
    building(repo)
    prompt = "\n".join([" ".join(f"w{i}" for i in range(4000))[:4000]] * 4)
    t = time.time()
    kind, _ = decision(fire(repo, prompt))
    assert kind == "deny" and time.time() - t < 3


def test_gate_does_not_read_a_relative_path_out_of_the_middle_of_an_absolute_path(tmp_path, monkeypatch):
    """別の repo の同じ slug の spec（dispatch 無し）を書いたとき、その中の docs/specs/<slug> を cwd の開いた spec と取り違えない。"""
    monkeypatch.setenv("SPEC_AUTOPILOT_HOME", str(tmp_path / ".autopilot-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude-config"))
    roots = []
    for name in ("open repo", "closed repo"):
        root = tmp_path / name
        root.mkdir()
        subprocess.run(GIT[:1] + ["init", "-q", str(root)], check=True)
        roots.append((root, building(root)))
    dispatched(*roots[0])
    kind, _ = decision(fire(roots[0][0], f"spec は {roots[1][1]} です"))
    assert kind == "deny"


def fresh_repo(tmp_path, monkeypatch, dirname):
    monkeypatch.setenv("SPEC_AUTOPILOT_HOME", str(tmp_path / ".autopilot-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude-config"))
    root = tmp_path / dirname
    root.mkdir(parents=True)
    subprocess.run(GIT[:1] + ["init", "-q", str(root)], check=True)
    return root


@pytest.mark.parametrize("prompt", ["spec は {d} です。T1 を実装して", "{d}を実装して", "spec は「{d}」", "{d}/tasks.md の T1"])
def test_gate_allows_an_open_dispatch_under_an_nfd_named_dir_written_in_nfc(tmp_path, monkeypatch, prompt):
    """Finder などが NFD で保存した濁点・半濁点の名前の下の spec を、prompt が NFC で書いても引く（字ではなく stat で照らす）。"""
    import unicodedata
    root = fresh_repo(tmp_path, monkeypatch, unicodedata.normalize("NFD", "プロジェクト データ"))
    d = dispatched(root, building(root))
    if not (tmp_path / unicodedata.normalize("NFC", root.name)).exists():
        pytest.skip("このファイルシステムは正規化を問わない照合をしない")
    assert decision(fire(root, prompt.format(d=unicodedata.normalize("NFC", str(d))))) is None
    rel = unicodedata.normalize("NFC", str(d.relative_to(root)))
    assert decision(fire(root, f"./{rel} の T1")) is None


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root は権限を問わずに読める")
def test_gate_allows_an_open_dispatch_under_an_execute_only_ancestor(tmp_path, monkeypatch):
    """祖先の docs が実行だけ（0311、一覧を読めない）でも、stat で state.json を確かめて通す。"""
    root = fresh_repo(tmp_path, monkeypatch, "noread")
    d = dispatched(root, building(root))
    os.chmod(root / "docs", 0o311)
    try:
        assert decision(fire(root, f"spec は {d} です")) is None
        assert decision(fire(root, f"{d.relative_to(root)}を実装して")) is None
    finally:
        os.chmod(root / "docs", 0o755)


def test_gate_names_a_spec_once_even_if_an_inner_slash_also_reaches_it(repo):
    """絶対パスの中の `/`（macOS の /private/var の中の /var など）からも同じ spec に届いても、deny の理由に 1 度だけ出す。"""
    d = building(repo)
    real = os.path.realpath(d)
    _, why = decision(fire(repo, f"spec は {real} と {d} です"))
    assert why.count(d.name) == 1, why


def test_gate_takes_the_spec_dir_name_as_the_anchor_and_ignores_other_paths(repo):
    """手がかり（docs/specs/<日付>-<slug>）の無いパスは、state.json があっても spec として拾わない。"""
    d = dispatched(repo, building(repo))
    link = repo / "plainlink"
    link.symlink_to(d, target_is_directory=True)
    kind, why = decision(fire(repo, f"spec は {link} です"))
    assert kind == "deny" and "spec のディレクトリ" in why


@pytest.mark.parametrize("cwd_rel, repo_rel, prompt", [
    ("top", "top/sub", "spec は {rel} です。T1 を実装して"),
    ("root", "root/.claude/worktrees/wt1", "{rel}を実装して"),
    ("a", "b", "spec は「{rel}」の T1"),
    ("a", "b", "{rel}/tasks.md の T1"),
])
def test_gate_resolves_a_relative_path_with_dirs_before_docs_specs_from_the_payload_cwd(tmp_path, monkeypatch, cwd_rel, repo_rel, prompt):
    """prompt の相対パスの、docs/specs の前に付いたディレクトリ（sub/・.claude/worktrees/wt1/・../b/）も payload の cwd から引く。"""
    root = fresh_repo(tmp_path, monkeypatch, repo_rel)
    d = dispatched(root, building(root))
    cwd = tmp_path / cwd_rel
    cwd.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(d, cwd)
    assert not rel.startswith("docs/")
    assert decision(fire(cwd, prompt.format(rel=rel))) is None


def test_gate_denies_a_relative_path_with_dirs_before_docs_specs_when_its_dispatch_is_closed(tmp_path, monkeypatch):
    """cwd から引いた相対パスの spec に開いた dispatch が無ければ、cwd の下の同じ名前の開いた spec と取り違えず deny する。"""
    top = fresh_repo(tmp_path, monkeypatch, "top")
    opened = dispatched(top, building(top))
    sub = top / "sub"
    sub.mkdir()
    subprocess.run(GIT[:1] + ["init", "-q", str(sub)], check=True)
    closed = building(sub)
    assert closed.name == opened.name
    kind, _ = decision(fire(top, f"spec は {closed.relative_to(top)} です"))
    assert kind == "deny"
