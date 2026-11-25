"""要件の high の後、評価役が書いた inputs/R<n>.md（落ちた入力の種類の表）を dispatch・handoff・check が検査する。"""
import subprocess

import pytest

from test_autopilot import implementer_ran, repo, run, state  # noqa: F401（repo は fixture）
from test_ladder import done_spec, high
from test_overnight import night

HEAD = "| 入力の種類 | 例 | 期待 | 今の結果 | テスト |\n|---|---|---|---|---|\n"
GOOD = HEAD + "| 絶対パス | /a/spec.md | 通る | fail | - |\n| 相対パス | a/spec.md | 通る | pass | - |\n"
NONE = "- 入力の種類: なし（テストが無いだけで、入力の形ではない）\n"


def put(d, text, rid="R1"):
    (d / "inputs").mkdir(exist_ok=True)
    (d / "inputs" / f"{rid}.md").write_text(text, encoding="utf-8")


def dispatch(repo, d):
    return night(repo, "dispatch", str(d), "--task", "T1")


def after_high(repo, text=None):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    if text is not None:
        put(d, text)
    high(repo, d)
    return d


def refused(repo, d, *want):
    n = len(state(d).get("dispatches") or [])
    r = dispatch(repo, d)
    assert r.returncode != 0, r.stdout
    assert str(d / "inputs" / "R1.md") in r.stdout or "が無い" in r.stdout
    for w in want:
        assert w in r.stdout, r.stdout
    assert len(state(d).get("dispatches") or []) == n


def test_dispatch_after_high_refuses_when_the_table_file_is_missing(repo):
    refused(repo, after_high(repo), "inputs/R1.md")


def test_dispatch_after_high_refuses_a_table_with_one_row(repo):
    refused(repo, after_high(repo, HEAD + "| 絶対 | /a | 通る | fail | - |\n"), "1 行")


def test_dispatch_after_high_refuses_a_row_with_an_empty_cell(repo):
    refused(repo, after_high(repo, HEAD + "| 絶対 | /a |  | fail | - |\n| 相対 | a | 通る | pass | - |\n"), "空")


def test_dispatch_after_high_refuses_a_result_other_than_pass_or_fail(repo):
    refused(repo, after_high(repo, HEAD + "| 絶対 | /a | 通る | fail | - |\n| 相対 | a | 通る | たぶん | - |\n"), "pass・fail でない")


def test_dispatch_after_high_refuses_a_table_without_a_fail_row(repo):
    refused(repo, after_high(repo, HEAD + "| 絶対 | /a | 通る | pass | - |\n| 相対 | a | 通る | pass | - |\n"), "fail の行が 1 つも無い")


def test_dispatch_after_high_refuses_a_table_with_another_heading(repo):
    refused(repo, after_high(repo, "| 種類 | 例 |\n|---|---|\n| a | b |\n| c | d |\n"), "見出し")


def test_dispatch_after_high_takes_a_full_table_and_names_the_path_and_the_tests_to_write(repo):
    d = after_high(repo, GOOD)
    r = dispatch(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(d / "inputs" / "R1.md") in r.stdout and "テストの欄" in r.stdout
    assert state(d)["dispatches"][-1]["reqs"] == ["R1"]


def test_dispatch_after_high_takes_a_none_line_only_file(repo):
    d = after_high(repo, NONE)
    n = len(state(d)["dispatches"])
    assert dispatch(repo, d).returncode == 0
    assert len(state(d)["dispatches"]) == n + 1


def test_dispatch_after_a_round_without_high_needs_no_table(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    assert run(repo, "review", str(d), "--high", "none").returncode == 0
    assert dispatch(repo, d).returncode == 0


def commit(repo, msg="impl"):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "add", "-A", "--", ".", ":(exclude)docs/specs"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", msg], cwd=repo, check=True)


def handoff(repo, d):
    return night(repo, "handoff", str(d), "--task", "T1")


def dispatched(repo, text, tests):
    d = after_high(repo, text)
    r = dispatch(repo, d)
    assert r.returncode == 0, r.stdout
    implementer_ran(r.stdout.strip().splitlines()[-1])
    (repo / "test_rule.py").write_text("def test_absolute():\n    pass\n\n\ndef test_relative():\n    pass\n", encoding="utf-8")
    put(d, text.replace("| - |", "| {} |").format(*tests) if tests else text)
    commit(repo)
    return d


def test_handoff_refuses_a_row_whose_test_cell_is_a_dash(repo):
    d = dispatched(repo, GOOD, None)
    r = handoff(repo, d)
    assert r.returncode != 0 and "相対パス" in r.stdout + r.stderr
    assert len(state(d)["handoffs"]) == 1  # done_spec が閉じた 1 件のまま


def test_handoff_refuses_a_test_that_is_not_in_the_repo(repo):
    d = dispatched(repo, GOOD, ["test_rule.py::test_absolute", "test_rule.py::test_nowhere"])
    r = handoff(repo, d)
    assert r.returncode != 0 and "test_nowhere" in r.stdout + r.stderr
    assert len(state(d)["handoffs"]) == 1  # done_spec が閉じた 1 件のまま


def test_handoff_closes_when_every_row_names_a_test_in_the_repo(repo):
    d = dispatched(repo, GOOD, ["test_rule.py::test_absolute", "test_rule.py::test_relative"])
    r = handoff(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(state(d)["handoffs"]) == 2


@pytest.mark.parametrize("parked, errors", [(False, True), (True, False)])
def test_check_names_a_fail_row_left_in_the_table_unless_the_requirement_is_parked(repo, parked, errors):
    d = after_high(repo, GOOD)
    if parked:
        s = state(d)
        s["parked"] = [{"kind": "other", "op": "x", "reason": "x", "req": "R1", "at": 1}]
        (d / "state.json").write_text(__import__("json").dumps(s), encoding="utf-8")
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
    import overnight
    got = overnight.input_fail_errors(d, state(d))
    assert bool(got) == errors
    if errors:
        assert "R1" in got[0] and "絶対パス" in got[0] and "評価役を回し直" in got[0]


def test_check_passes_the_table_when_every_row_is_pass(repo):
    d = after_high(repo, GOOD.replace("fail", "pass"))
    r = run(repo, "check", str(d))
    assert "fail の行" not in r.stdout + r.stderr


def test_two_handoffs_at_once_leave_the_table_check_the_same(repo):
    d = dispatched(repo, GOOD, ["test_rule.py::test_absolute", "test_rule.py::test_relative"])
    rs = [handoff(repo, d), handoff(repo, d)]
    assert [r.returncode for r in rs] == [0, 0]
