"""autopilot.py goal <親>（受け持ちの表と、親の done）を、入口（CLI）から通して確かめる。
親は、要件が全部どれかの子の `- 親の要件:` に挙がり、挙げた子が全部 done のときだけ done になる。"""
import json
import os
import subprocess
import sys
from pathlib import Path

from test_autopilot import CLI, run, state, repo  # noqa: F401
from test_goal_child import child_spec, parent_goal


def set_phase(d, phase):
    s = state(d)
    s["phase"] = phase
    (d / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def rows():
    f = Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "runs.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def family(repo, children):
    """親と、(phase, 親の要件) ごとの子。"""
    parent = parent_goal(repo)
    ds = []
    for i, (phase, reqs) in enumerate(children):
        d = child_spec(repo, parent, slug=f"child{i}", reqs=reqs)
        set_phase(d, phase)
        ds.append(d)
    return parent, ds


def test_goal_marks_the_parent_done_when_every_requirement_has_a_done_child(repo):
    parent, (a, b) = family(repo, [("done", "R1"), ("done", "R2")])
    r = run(repo, "goal", str(parent))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "R1" in r.stdout and a.name in r.stdout and "R2" in r.stdout and b.name in r.stdout
    s = state(parent)
    assert s["phase"] == "done" and isinstance(s["done_at"], float) and s["goal"]["by"] == "目的 OK"
    (row,) = rows()
    assert row["kind"] == "done" and row["spec"] == parent.name
    assert isinstance(row["active_min"], float)  # 親に approved_at が無いので、目的の承認の時刻から数える


def test_goal_accepts_one_child_that_covers_several_requirements(repo):
    parent, _ = family(repo, [("done", "R1、R2")])
    assert run(repo, "goal", str(parent)).returncode == 0
    assert state(parent)["phase"] == "done"


def test_goal_refuses_while_a_child_is_not_done_and_names_it(repo):
    parent, (a, b) = family(repo, [("done", "R1"), ("queued", "R2")])
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and "ERROR" in r.stdout
    assert b.name in r.stdout and "queued" in r.stdout
    assert state(parent)["phase"] == "discovery" and "done_at" not in state(parent)
    assert rows() == []


def test_goal_refuses_a_requirement_no_child_takes(repo):
    parent, _ = family(repo, [("done", "R1")])
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and "ERROR" in r.stdout and "R2" in r.stdout and "子が無い" in r.stdout
    assert state(parent)["phase"] == "discovery" and rows() == []


def test_goal_lists_both_a_missing_requirement_and_a_child_that_is_not_done(repo):
    parent, (a,) = family(repo, [("building", "R1")])
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and "R2" in r.stdout and "子が無い" in r.stdout and a.name in r.stdout and "building" in r.stdout


def test_goal_ignores_children_of_another_parent_and_a_child_with_a_broken_requirement_line(repo):
    parent, _ = family(repo, [("done", "R1")])
    other = parent_goal(repo, "other")
    stray = child_spec(repo, other, slug="stray", reqs="R2")
    set_phase(stray, "done")
    broken = child_spec(repo, parent, slug="broken", reqs="R2、")
    set_phase(broken, "done")
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and "R2" in r.stdout and "子が無い" in r.stdout
    assert state(parent)["phase"] == "discovery"


def test_goal_refuses_a_spec_that_was_not_approved_as_a_goal(repo):
    from test_autopilot import init_spec
    d = init_spec(repo, "plain")
    r = run(repo, "goal", str(d))
    assert r.returncode == 1 and "目的として承認されていない" in r.stdout
    assert state(d)["phase"] == "discovery"


def test_goal_on_a_done_parent_adds_no_second_row(repo):
    parent, _ = family(repo, [("done", "R1、R2")])
    assert run(repo, "goal", str(parent)).returncode == 0
    done_at = state(parent)["done_at"]
    assert run(repo, "goal", str(parent)).returncode == 0
    assert len(rows()) == 1 and state(parent)["done_at"] == done_at


def test_goal_reads_the_children_at_call_time(repo):
    """前の呼び出しの表を持ち回さない: 子が done になった後の呼び出しで通る。"""
    parent, (a,) = family(repo, [("queued", "R1、R2")])
    assert run(repo, "goal", str(parent)).returncode == 1
    set_phase(a, "done")
    assert run(repo, "goal", str(parent)).returncode == 0


def test_two_goal_calls_at_once_write_one_done_row(repo):
    parent, _ = family(repo, [("done", "R1、R2")])
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    ps = [subprocess.Popen([sys.executable, str(CLI), "goal", str(parent)], cwd=repo, env=env, stdout=subprocess.PIPE, text=True) for _ in range(4)]
    assert [p.wait() for p in ps] == [0, 0, 0, 0]
    assert len(rows()) == 1 and state(parent)["phase"] == "done"


def test_goal_reports_a_child_whose_state_cannot_be_read_and_does_not_mark_the_parent_done(repo):
    parent, (a, b) = family(repo, [("done", "R1、R2"), ("done", "R2")])
    (b / "state.json").write_text("{broken", encoding="utf-8")
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and f"ERROR: {b.name} が読めない（JSONDecodeError）" in r.stdout, r.stdout + r.stderr
    assert state(parent)["phase"] == "discovery" and rows() == []


def test_goal_reports_a_child_whose_spec_cannot_be_read_and_does_not_mark_the_parent_done(repo):
    parent, (a, b) = family(repo, [("done", "R1、R2"), ("done", "R2")])
    (b / "spec.md").write_bytes(b"\xff\xfe\x00broken")
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and f"ERROR: {b.name} が読めない（UnicodeDecodeError）" in r.stdout, r.stdout + r.stderr
    assert state(parent)["phase"] == "discovery" and rows() == []


def test_goal_leaves_no_untracked_file_in_the_spec_directory(repo):
    parent, (a,) = family(repo, [("queued", "R1、R2")])
    before = sorted(x.name for x in parent.iterdir())
    assert run(repo, "goal", str(parent)).returncode == 1
    assert sorted(x.name for x in parent.iterdir()) == before
    set_phase(a, "done")
    assert run(repo, "goal", str(parent)).returncode == 0
    assert sorted(x.name for x in parent.iterdir()) == before
    assert run(repo, "goal", str(parent)).returncode == 0
    assert sorted(x.name for x in parent.iterdir()) == before


def test_goal_on_a_missing_directory_is_one_error_line_not_a_traceback(repo):
    r = run(repo, "goal", str(repo / "docs" / "specs" / "2026-01-01-nothing"))
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and "2026-01-01-nothing" in r.stdout, r.stdout + r.stderr
    assert "Traceback" not in r.stderr and r.stdout.count("\n") == 1


def test_goal_table_follows_the_requirement_order_of_the_parent_spec(repo):
    parent = parent_goal(repo)
    order = ["R3", "R1", "R2", "R5", "R4", "R7", "R6"]
    text = (parent / "spec.md").read_text(encoding="utf-8")
    body = "".join(f"- {r}: 要件 {r}。\n" for r in order)
    (parent / "spec.md").write_text(text.replace("- R1: 横 1 列がそろったとき、ゲームはその列を消す。\n- R2: ゲームオーバーのとき、Enter で再開できる。\n", body), encoding="utf-8")
    for seed in ("0", "1", "2", "3", "4"):
        r = subprocess.run([sys.executable, str(CLI), "goal", str(parent)], cwd=repo, capture_output=True, text=True,
                           env={**os.environ, "CLAUDE_CODE_SESSION_ID": "s1", "PYTHONHASHSEED": seed})
        shown = [x.split(":")[0] for x in r.stdout.splitlines() if x[:1] == "R"]
        assert shown == order, (seed, r.stdout)
