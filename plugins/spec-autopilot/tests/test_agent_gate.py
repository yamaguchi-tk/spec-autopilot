"""hooks/agent_gate.py（実装役の起動の入口で、開いた dispatch の無い起動を deny する PreToolUse hook）を、
payload を stdin で渡す入口と、hooks.json の command（答えを出さずに終わったときの deny）から確かめる。"""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from test_autopilot import PLUGIN, implementer_ran, init_spec, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_overnight import full_spec, night

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


def test_gate_records_a_reviewer_launch_in_the_building_spec_and_allows_it(repo):
    d = building(repo)
    assert not state(d).get("review_launches")
    before = time.time()
    assert decision(fire(repo, f"spec: {d}。base..tip を評価して", agent=REVIEWER)) is None
    launches = state(d)["review_launches"]
    assert len(launches) == 1 and launches[0] >= before
    assert decision(fire(repo, f"spec: {d}", agent="autopilot-reviewer-fable")) is None
    assert len(state(d)["review_launches"]) == 2


def test_gate_leaves_state_alone_when_the_reviewer_names_no_building_spec(repo):
    d = building(repo)
    other = init_spec(repo, "draft")  # discovery
    before = {p: (p / "state.json").read_bytes() for p in (d, other)}
    assert decision(fire(repo, "評価して", agent=REVIEWER)) is None
    assert decision(fire(repo, f"spec: {other}", agent=REVIEWER)) is None
    assert {p: (p / "state.json").read_bytes() for p in (d, other)} == before


def test_gate_denies_an_implementer_while_a_reviewer_result_is_not_recorded(repo):
    d = dispatched(repo, building(repo))
    assert decision(fire(repo, f"{d}")) is None
    assert decision(fire(repo, f"{d}", agent=REVIEWER)) is None
    kind, why = decision(fire(repo, f"{d}"))
    assert kind == "deny" and "autopilot.py review" in why and str(d) in why
    assert run(repo, "review", str(d), "--high", "none").returncode == 0
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
