"""大きさ S の spec で、承認の前（discovery）に実装役の試作を起動できる門（overnight.py dispatch・hooks/agent_gate.py・承認の持ち越し・handoff）を、
入口（CLI と hook）から通して確かめる。"""
import json
import subprocess
import sys

import pytest

from test_agent_gate import GIT, IMPL, decision, fire
from test_autopilot import GOOD_SPEC, implementer_ran, init_spec, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_lineup import line
from test_overnight import night

TASKS = "# タスク\n\n- [ ] T1: 規則 [R1, R2]\n"


def draft(repo, size="- 大きさ: S", slug="game"):
    d = init_spec(repo, slug)
    text = GOOD_SPEC.replace("- 大きさ: S", size) if size is not None else GOOD_SPEC.replace("- 大きさ: S\n", "")
    (d / "spec.md").write_text(text, encoding="utf-8")
    (d / "tasks.md").write_text(TASKS, encoding="utf-8")
    assert state(d)["phase"] == "discovery"
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


@pytest.mark.parametrize("size", ["- 大きさ: M", "- 大きさ: L", None, "- 大きさ: 小", "- 大きさ: S\n- 大きさ: S"])
def test_dispatch_in_discovery_refuses_a_spec_that_is_not_small_and_keeps_state(repo, size):
    d = draft(repo, size)
    before = (d / "state.json").read_text(encoding="utf-8")
    r = dispatch(repo, d)
    assert r.returncode != 0
    assert (d / "state.json").read_text(encoding="utf-8") == before


def test_gate_allows_the_implementer_dispatched_in_discovery(repo):
    d = draft(repo)
    assert dispatch(repo, d).returncode == 0
    assert decision(fire(repo, f"spec: {d}。T1")) is None


@pytest.mark.parametrize("size", ["- 大きさ: M", "- 大きさ: L", None])
def test_gate_denies_in_discovery_when_the_size_is_not_small_even_with_a_dispatch_record(repo, size):
    d = draft(repo, size)
    st = state(d)
    st["dispatches"] = [{"base": None, "tasks": ["T1"], "reqs": ["R1"], "agent": "autopilot-implementer", "at": 1}]
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    kind, _ = decision(fire(repo, f"{d}"))
    assert kind == "deny"


def test_gate_denies_in_discovery_for_a_small_spec_without_a_dispatch(repo):
    kind, why = decision(fire(repo, f"{draft(repo)}"))
    assert kind == "deny" and "overnight.py dispatch" in why


def test_gate_denies_in_discovery_an_implementer_of_another_rung(repo):
    d = draft(repo)
    assert dispatch(repo, d).returncode == 0
    kind, _ = decision(fire(repo, f"{d}", agent="spec-autopilot:autopilot-implementer-fable"))
    assert kind == "deny"


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
