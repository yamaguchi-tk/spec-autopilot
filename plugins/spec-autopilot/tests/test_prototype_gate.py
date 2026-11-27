"""大きさ S の spec と、新しく作る repo で依る spec の無い大きさ M の spec で、承認の前（discovery）に実装役の試作を起動できる門（overnight.py dispatch・hooks/agent_gate.py・承認の持ち越し・handoff）を、
入口（CLI と hook）から通して確かめる。"""
import json
import subprocess
import sys
import time

import pytest

from test_agent_gate import GIT, IMPL, decision, fire
from test_autopilot import GOOD_SPEC, NOT_FALSE, implementer_ran, init_spec, repo, run, state, user_says, with_existing  # noqa: F401（repo は fixture）
from test_lineup import line
from test_overnight import night

TASKS = "# タスク\n\n- [ ] T1: 規則 [R1, R2]\n"


DEPENDENT_M = "- 大きさ: M\n- 依る spec: 2026-01-01-base"


def draft(repo, size="- 大きさ: S", slug="game", existing=False):
    if existing:  # git が追うコードのある repo にしてから init する（state.json の existing が真になる）
        (repo / "app.py").write_text("print('hi')\n", encoding="utf-8")
        subprocess.run([*GIT, "add", "app.py"], cwd=repo, check=True)
        subprocess.run([*GIT, "commit", "-q", "-m", "app"], cwd=repo, check=True)
    d = init_spec(repo, slug)
    text = GOOD_SPEC.replace("- 大きさ: S", size) if size is not None else GOOD_SPEC.replace("- 大きさ: S\n", "")
    (d / "spec.md").write_text(text, encoding="utf-8")
    (d / "tasks.md").write_text(TASKS, encoding="utf-8")
    assert state(d)["phase"] == "discovery" and bool(state(d).get("existing")) == existing
    return d


def dispatch(repo, d):
    return night(repo, "dispatch", str(d), "--task", "T1")


def implement(repo, d):
    """dispatch した実装役が起動して commit した状態にする。"""
    r = dispatch(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    implementer_ran(r.stdout.strip().splitlines()[-1])
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    return r


def test_dispatch_in_discovery_accepts_a_small_spec_and_prints_the_implementer(repo):
    d = draft(repo)
    r = dispatch(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "autopilot-implementer"
    assert len(state(d)["dispatches"]) == 1


def test_dispatch_in_discovery_accepts_a_medium_spec_in_a_new_repo_and_prints_the_implementer(repo):
    d = draft(repo, "- 大きさ: M")
    r = dispatch(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "autopilot-implementer"
    assert len(state(d)["dispatches"]) == 1


# 大きさの行が 2 行ある spec は、S でも M でも試作を拒む（PR 92 で S の場合が表から消えたので戻した）。
# 範囲: この表と下の hook の表に、大きさの行が 2 行ある場合を足すだけで、門の判定は変えない。想定する脅威: 事故（大きさの行を 2 つ書いた spec）だけ。
# やらないこと: existing の読み方を変えること（PR 97 で直した）。
@pytest.mark.parametrize("size, existing", [
    ("- 大きさ: M", True), (DEPENDENT_M, False), ("- 大きさ: L", False), (None, False), ("- 大きさ: 小", False), ("- 大きさ: S\n- 大きさ: S", False), ("- 大きさ: M\n- 大きさ: M", False)])
def test_dispatch_in_discovery_refuses_a_spec_that_is_not_allowed_a_prototype_and_keeps_state(repo, size, existing):
    d = draft(repo, size, existing=existing)
    before = (d / "state.json").read_text(encoding="utf-8")
    r = dispatch(repo, d)
    assert r.returncode != 0
    assert (d / "state.json").read_text(encoding="utf-8") == before


def test_dispatch_in_discovery_accepts_a_small_spec_in_an_existing_repo(repo):
    d = draft(repo, existing=True)
    assert dispatch(repo, d).returncode == 0


def test_gate_allows_the_implementer_dispatched_in_discovery(repo):
    d = draft(repo)
    assert dispatch(repo, d).returncode == 0
    assert decision(fire(repo, f"spec: {d}。T1")) is None


def test_gate_allows_the_implementer_dispatched_for_a_medium_spec_in_a_new_repo(repo):
    d = draft(repo, "- 大きさ: M")
    assert dispatch(repo, d).returncode == 0
    assert decision(fire(repo, f"spec: {d}。T1")) is None


@pytest.mark.parametrize("size, existing", [
    ("- 大きさ: M", True), (DEPENDENT_M, False), ("- 大きさ: L", False), (None, False), ("- 大きさ: S\n- 大きさ: S", False), ("- 大きさ: M\n- 大きさ: M", False)])
def test_gate_denies_in_discovery_when_no_prototype_is_allowed_even_with_a_dispatch_record(repo, size, existing):
    d = draft(repo, size, existing=existing)
    st = state(d)
    st["dispatches"] = [{"base": None, "tasks": ["T1"], "reqs": ["R1"], "agent": "autopilot-implementer", "at": 1}]
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    out = decision(fire(repo, f"{d}"))
    assert out is not None and out[0] == "deny"


def test_gate_denies_in_discovery_for_a_small_spec_without_a_dispatch(repo):
    out = decision(fire(repo, f"{draft(repo)}"))
    assert out is not None and out[0] == "deny" and "overnight.py dispatch" in out[1]


def test_gate_denies_in_discovery_an_implementer_of_another_rung(repo):
    d = draft(repo)
    assert dispatch(repo, d).returncode == 0
    out = decision(fire(repo, f"{d}", agent="spec-autopilot:autopilot-implementer-fable"))
    assert out is not None and out[0] == "deny"


def test_handoff_closes_the_prototype_dispatch_after_approval(repo):
    d = draft(repo)
    implement(repo, d)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    s = state(d)
    assert s["phase"] == "building" and s["handoffs"][-1]["dispatch"] == 0


def test_handoff_closes_the_prototype_dispatch_of_a_medium_spec_in_a_new_repo_after_approval(repo):
    d = draft(repo, "- 大きさ: M")
    implement(repo, d)
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["handoffs"][-1]["dispatch"] == 0


def test_handoff_closes_the_prototype_dispatch_after_a_queued_approval_starts(repo):
    d = draft(repo)
    implement(repo, d)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    assert line(repo, "next").returncode == 0
    assert state(d)["phase"] == "building"
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["handoffs"][-1]["dispatch"] == 0


def test_queued_approval_blocked_at_start_keeps_the_prototype_dispatch_after_the_next_approve(repo):
    d = draft(repo)
    implement(repo, d)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8") + "\n変更\n", encoding="utf-8")
    line(repo, "next")
    assert state(d)["phase"] == "blocked"
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    assert len(state(d)["dispatches"]) == 1
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr


def test_requeued_approval_after_a_start_block_keeps_the_prototype_dispatch_and_handoff_closes_it(repo):
    d = draft(repo)
    implement(repo, d)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8") + "\n変更\n", encoding="utf-8")
    line(repo, "next")
    assert state(d)["phase"] == "blocked"
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    assert line(repo, "next").returncode == 0
    assert state(d)["phase"] == "building" and len(state(d)["dispatches"]) == 1
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["handoffs"][-1]["dispatch"] == 0


@pytest.mark.parametrize("queue", [False, True])
@pytest.mark.parametrize("after", ["done", "blocked"])
def test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history(repo, after, queue):
    d = draft(repo)
    implement(repo, d)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    (d / "tasks.md").write_text(TASKS.replace("[ ]", "[x]"), encoding="utf-8")
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0
    st = state(d)
    assert len(st["dispatches"]) == 1 and len(st["handoffs"]) == 1
    st.update(phase=after, done_at=time.time(), blocked={"req": "R1", "reason": "x", "evidence": "y", "at": time.time()} if after == "blocked" else None)
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK", *(["--queue"] if queue else []))
    assert r.returncode == 0, r.stdout + r.stderr
    if queue:
        assert line(repo, "next").returncode == 0
    s = state(d)
    assert s["phase"] == "building"
    assert not s.get("dispatches") and not s.get("handoffs")
    assert any(len(h.get("dispatches") or []) == 1 and len(h.get("handoffs") or []) == 1 for h in s["history"]), s["history"]


def test_dispatch_and_gate_say_that_spec_md_could_not_be_read(repo):
    d = draft(repo)
    (d / "spec.md").chmod(0)
    try:
        r = dispatch(repo, d)
        out = decision(fire(repo, f"{d}"))
    finally:
        (d / "spec.md").chmod(0o644)
    assert r.returncode != 0 and "spec.md が読めない" in r.stdout + r.stderr
    assert out is not None and out[0] == "deny" and "spec.md が読めない" in out[1]


@pytest.mark.parametrize("value", NOT_FALSE)
def test_dispatch_in_discovery_refuses_a_medium_spec_when_existing_is_not_false_and_keeps_state(repo, value):
    d = draft(repo, "- 大きさ: M")
    with_existing(d, value)
    before = (d / "state.json").read_text(encoding="utf-8")
    r = dispatch(repo, d)
    assert r.returncode != 0
    assert (d / "state.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("value", NOT_FALSE)
def test_gate_denies_in_discovery_a_medium_spec_when_existing_is_not_false_even_with_a_dispatch_record(repo, value):
    d = draft(repo, "- 大きさ: M")
    st = state(d)
    st["dispatches"] = [{"base": None, "tasks": ["T1"], "reqs": ["R1"], "agent": "autopilot-implementer", "at": 1}]
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    with_existing(d, value)
    out = decision(fire(repo, f"{d}"))
    assert out is not None and out[0] == "deny"
