"""done・block の記録（runs.jsonl）を、入口の CLI から通して確かめる。"""
import json
import os
import re
from pathlib import Path

import pytest

from test_autopilot import approved, make_done, repo, run, state  # noqa: F401


def log_file():
    return Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "runs.jsonl"


def rows():
    f = log_file()
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def block(repo, d, reason="x"):
    return run(repo, "block", str(d), "--req", "R1", "--reason", reason, "--evidence", "y")


def test_done_appends_one_row_with_all_keys(repo):
    d = approved(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    (row,) = rows()
    assert set(row) == {"kind", "at", "spec", "repo", "active_min", "total_min", "size", "blocks", "rework_of", "prs", "light"}
    assert row["kind"] == "done" and row["spec"] == d.name and row["repo"] == str(repo.resolve())
    assert row["size"] == "S" and row["blocks"] == [] and row["rework_of"] is None and row["prs"] == [] and row["light"] is False


def test_done_on_a_done_spec_adds_no_row(repo):
    d = approved(repo)
    make_done(repo, d)
    run(repo, "done", str(d))
    run(repo, "done", str(d))
    assert len(rows()) == 1


def test_block_appends_a_block_row_with_this_block(repo):
    d = approved(repo)
    assert block(repo, d, "壊れた").returncode == 0
    (row,) = rows()
    assert row["kind"] == "block" and row["blocks"] == [{"req": "R1", "reason": "壊れた"}]
    assert row["active_min"] is not None and row["prs"] == []


def test_block_while_waiting_counts_active_time_until_the_wait_began(repo):
    d = approved(repo)
    s = state(d)
    s.update(approved_at=1000.0, created_at=1000.0, phase="wait", wait={"reason": "r", "at": 1600.0})
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert block(repo, d).returncode == 0
    assert rows()[0]["active_min"] == 10.0


def test_rework_of_is_read_from_the_constraints(repo):
    d = approved(repo)
    p = d / "spec.md"
    p.write_text(p.read_text(encoding="utf-8").replace("- 大きさ: S", "- 大きさ: S\n- 手戻り元: 2026-11-01-x"), encoding="utf-8")
    assert block(repo, d).returncode == 0
    assert rows()[0]["rework_of"] == "2026-11-01-x"


def test_prs_lists_recorded_merges(repo):
    d = approved(repo)
    s = state(d)
    s["merges"] = [{"pr": 7}, {"pr": 9}]
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    block(repo, d)
    assert rows()[0]["prs"] == [7, 9]


@pytest.mark.parametrize("cmd", ["done", "block"])
def test_unwritable_runs_log_is_a_note_and_exit_zero(repo, cmd):
    d = approved(repo)
    log_file().mkdir(parents=True)
    if cmd == "done":
        make_done(repo, d)
        r = run(repo, "done", str(d))
    else:
        r = block(repo, d)
    assert r.returncode == 0, r.stderr
    assert re.search(r"NOTE: runs\.jsonl", r.stdout)


# --- T2: 再承認をまたぐ active_min と、着手の時点の block ---

def test_active_min_sums_rounds_minus_paused_sec_across_reapproval(repo):
    from test_autopilot import user_says
    d = approved(repo)
    s = state(d)
    s.update(approved_at=1000.0, created_at=1000.0, paused_sec=60)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert block(repo, d).returncode == 0
    s = state(d)
    s["blocked"]["at"] = 1600.0
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    assert state(d)["history"][-1]["paused_sec"] == 60 and state(d)["paused_sec"] == 0
    import time
    s = state(d)
    s["approved_at"] = time.time() - 1200
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    done = [r for r in rows() if r["kind"] == "done"][0]
    assert abs(done["active_min"] - 29.0) < 0.3  # (1600-1000-60)/60 + 20
    assert done["blocks"] == [{"req": "R1", "reason": "x"}]


def lineup_next(repo):
    import subprocess
    import sys
    from test_lineup import LINEUP
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(LINEUP), "next"], cwd=repo, capture_output=True, text=True, env=env, timeout=60)


def queue_one(repo, d):
    from test_autopilot import user_says
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK", "--queue")
    assert r.returncode == 0, r.stdout + r.stderr


def change(d):
    p = d / "spec.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n<!-- 変更 -->\n", encoding="utf-8")


def test_lineup_next_block_at_start_appends_row_with_null_active_min_when_no_earlier_round(repo):
    from test_autopilot import init_spec
    d = init_spec(repo)
    queue_one(repo, d)
    change(d)
    assert lineup_next(repo).returncode == 0
    (row,) = rows()
    assert row["kind"] == "block" and row["active_min"] is None and row["spec"] == d.name
    assert len(row["blocks"]) == 1 and row["blocks"][0]["req"] == "着手"


def test_lineup_next_block_at_start_keeps_earlier_round_active_min_and_block(repo):
    d = approved(repo)
    s = state(d)
    s.update(approved_at=1000.0, created_at=1000.0, paused_sec=0)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    block(repo, d, "前")
    s = state(d)
    s["blocked"]["at"] = 1600.0
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    queue_one(repo, d)
    change(d)
    assert lineup_next(repo).returncode == 0
    last = rows()[-1]
    assert last["kind"] == "block" and last["active_min"] == 10.0
    assert [b["reason"] for b in last["blocks"]][0] == "前" and len(last["blocks"]) == 2


def test_lineup_next_block_at_start_is_a_note_when_runs_log_is_unwritable(repo):
    from test_autopilot import init_spec
    d = init_spec(repo)
    queue_one(repo, d)
    change(d)
    log_file().mkdir(parents=True)
    r = lineup_next(repo)
    assert r.returncode == 0 and "NOTE: runs.jsonl" in r.stdout


def seed_blocked_round(repo, d):
    s = state(d)
    s.update(approved_at=1000.0, created_at=1000.0, paused_sec=0)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    block(repo, d, "前")
    s = state(d)
    s["blocked"]["at"] = 1600.0
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")


def test_block_at_start_then_reapproval_then_done_keeps_both_blocks_and_active_min(repo):
    import time
    d = approved(repo)
    seed_blocked_round(repo, d)
    queue_one(repo, d)
    change(d)
    assert lineup_next(repo).returncode == 0
    queue_one(repo, d)
    assert lineup_next(repo).returncode == 0 and state(d)["phase"] == "building"
    from test_autopilot import make_done
    s = state(d)
    s["approved_at"] = time.time() - 1200
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    done = [r for r in rows() if r["kind"] == "done"][-1]
    assert [b["req"] for b in done["blocks"]] == ["R1", "着手"]
    assert abs(done["active_min"] - 30.0) < 0.3


def test_two_blocks_at_start_in_a_row_keep_every_block(repo):
    d = approved(repo)
    seed_blocked_round(repo, d)
    queue_one(repo, d)
    change(d)
    assert lineup_next(repo).returncode == 0
    queue_one(repo, d)
    change(d)
    assert lineup_next(repo).returncode == 0
    last = rows()[-1]
    assert [b["req"] for b in last["blocks"]] == ["R1", "着手", "着手"]
    assert last["active_min"] == 10.0
