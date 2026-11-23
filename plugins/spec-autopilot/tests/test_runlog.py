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
    assert set(row) == {"kind", "at", "spec", "repo", "active_min", "total_min", "size", "blocks", "rework_of", "prs"}
    assert row["kind"] == "done" and row["spec"] == d.name and row["repo"] == str(repo.resolve())
    assert row["size"] == "S" and row["blocks"] == [] and row["rework_of"] is None and row["prs"] == []


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
