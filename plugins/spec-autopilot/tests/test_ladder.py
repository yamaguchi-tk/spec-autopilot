"""難しい実装で段（モデルと effort）を上げる仕組みを、CLI の入口から確かめる。
実装役の段は、CLI が記録した事実（review の巡の streak と fail --from impl）から要件ごとに自動で上げる。"""
import json
import re
from pathlib import Path

import pytest

from test_autopilot import approved, hand_off, init_spec, make_done, repo, run, state  # noqa: F401（repo は fixture）
from test_overnight import night

AGENTS = Path(__file__).resolve().parents[1] / "agents"


def agent_of(repo, d, role, *tasks):
    r = night(repo, "agent", str(d), "--role", role, *[a for t in tasks for a in ("--task", t)])
    return r


def name(r):
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip().splitlines()[-1]


def impl_fail(repo, d, req="R1"):
    assert run(repo, "fail", str(d), "--req", req, "--from", "impl", "--evidence", "満たせなかった").returncode == 0


def high(repo, d, reqs="R1"):
    for q in reqs.split(","):  # 評価役が書く入力の種類の表（入力の形でない high は「なし」の 1 行）
        (d / "inputs").mkdir(exist_ok=True)
        (d / "inputs" / f"{q}.md").write_text("- 入力の種類: なし（テスト用）\n", encoding="utf-8")
    r = run(repo, "review", str(d), "--high", reqs)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def done_spec(repo, tasks="- [x] T1: 規則のモジュール [R1, R2]\n"):
    d = approved(repo)
    make_done(repo, d)
    (d / "tasks.md").write_text("# タスク\n\n" + tasks, encoding="utf-8")
    return d


def test_the_default_agents_are_the_measured_pair(repo):
    d = done_spec(repo)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer"
    assert name(agent_of(repo, d, "review")) == "autopilot-reviewer"


def test_a_failure_of_the_implementer_raises_its_requirement_at_once(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n- [x] T2: 表示 [R2]\n")
    impl_fail(repo, d)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-high"  # 次のレビューを待たずに作り直す
    impl_fail(repo, d)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-high"  # 上げた段をまだ渡していない
    assert name(agent_of(repo, d, "impl", "T2")) == "autopilot-implementer"  # 上げるのはその要件のタスクだけ


def test_each_dispatch_that_fails_raises_one_more_rung_within_a_round(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    seen = []
    for _ in range(2):
        assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
        impl_fail(repo, d)  # 渡した段でも満たせなかった（レビューの巡はまだ）
        seen.append(name(agent_of(repo, d, "impl", "T1")))
    assert seen == ["autopilot-implementer-high", "autopilot-implementer-opus"]


def test_a_review_round_raises_again_after_the_raised_rung_was_dispatched(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    high(repo, d)
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    impl_fail(repo, d)  # low→high
    hand_off(repo, d)  # 上げた段で渡し直した
    high(repo, d)  # 2 巡目（原因調査）
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-opus"


def test_the_dead_end_ladder_raises_without_main_calling_anything(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    seen = []
    for _ in range(3):
        high(repo, d)
        seen.append(name(agent_of(repo, d, "impl", "T1")))
    # 1 巡目: 上げない。2 巡目（原因調査）・3 巡目（作り直し）で 1 段ずつ
    assert seen == ["autopilot-implementer", "autopilot-implementer-high", "autopilot-implementer-opus"]


def test_one_round_raises_one_rung_even_with_several_signals(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    high(repo, d)
    impl_fail(repo, d)
    high(repo, d)  # 原因調査と実装役の失敗が同じ巡に当たる
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-high"
    assert len([r for r in state(d)["raises"] if r["req"] == "R1"]) == 1


def test_a_task_takes_the_highest_rung_of_its_requirements(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1, R2]\n")
    impl_fail(repo, d, "R2")
    run(repo, "review", str(d), "--high", "none")
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-high"


def test_the_rung_survives_a_rewrite_of_tasks_md(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    impl_fail(repo, d)
    run(repo, "review", str(d), "--high", "none")
    (d / "tasks.md").write_text("# タスク\n\n- [x] T7: 作り直した規則 [R1]\n", encoding="utf-8")
    assert name(agent_of(repo, d, "impl", "T7")) == "autopilot-implementer-high"


def raise_rounds(repo, d, n, req="R1"):
    for _ in range(n):
        impl_fail(repo, d, req)
        run(repo, "review", str(d), "--high", "none")


def test_fable_comes_only_after_two_failures_at_the_top_opus_and_runs_once(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    raise_rounds(repo, d, 3)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-opus-xhigh"
    raise_rounds(repo, d, 1)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-opus-xhigh"  # 1 回目はそのまま
    raise_rounds(repo, d, 1)
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-fable"
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0 and "autopilot-implementer-fable" in r.stdout
    impl_fail(repo, d)  # Fable でも満たせなかった
    for cmd in (["dispatch"], ["agent", "--role", "impl"]):
        r = night(repo, *cmd, str(d), "--task", "T1")
        assert r.returncode == 1 and "park" in r.stdout


def test_a_failure_at_fable_parks_the_requirement(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    raise_rounds(repo, d, 6)
    r = agent_of(repo, d, "impl", "T1")
    assert r.returncode == 1 and "park" in r.stdout


def test_dispatch_prints_and_records_the_agent(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    raise_rounds(repo, d, 1)
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "autopilot-implementer-high"
    assert state(d)["dispatches"][-1]["agent"] == "autopilot-implementer-high"


def test_the_reviewer_goes_up_by_hand_when_the_verdict_is_not_decided_and_tries_fable_once(repo):
    d = done_spec(repo)
    for _ in range(2):
        assert night(repo, "raise", str(d), "--role", "review", "--reason", "判定が決まらない").returncode == 0
    assert name(agent_of(repo, d, "review")) == "autopilot-reviewer-fable"
    run(repo, "review", str(d), "--high", "none")  # Fable で 1 回レビューした
    assert name(agent_of(repo, d, "review")) == "autopilot-reviewer-xhigh"


@pytest.mark.parametrize("args", [["--role", "impl", "--reason", "BLOCKED", "--task", "T1"],
                                  ["--role", "review", "--reason", "なんとなく"]])
def test_raise_takes_only_the_reviewer_signal(repo, args):
    d = done_spec(repo)
    assert night(repo, "raise", str(d), *args).returncode != 0
    assert not state(d).get("raises")


def test_the_spec_can_start_a_role_higher(repo):
    d = init_spec(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## モデル\n\n- 実装: opus-medium\n- 評価: opus-xhigh\n", encoding="utf-8")
    (d / "tasks.md").write_text("# タスク\n\n- [ ] T1: 規則 [R1]\n", encoding="utf-8")
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-opus"
    assert name(agent_of(repo, d, "review")) == "autopilot-reviewer-xhigh"
    assert "モデル" not in run(repo, "lint", str(d)).stdout


@pytest.mark.parametrize("row", ["- 評価: sonnet-high", "- 実装: gpt", "- 評価: なんでも"])
def test_lint_refuses_an_unknown_rung_or_a_reviewer_below_the_default(repo, row):
    d = init_spec(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + f"\n## モデル\n\n{row}\n", encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode != 0
    assert "モデル" in r.stdout


def test_the_report_counts_a_raised_requirement_as_passed_only_by_a_later_review(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n- [x] T2: 表示 [R2]\n")
    raise_rounds(repo, d, 1, "R1")
    raise_rounds(repo, d, 1, "R2")
    high(repo, d, "R2")  # R1 は上げた後のレビューで high が無い。R2 は上げた後も high
    out = night(repo, "report", str(d)).stdout
    assert re.search(r"段を上げたタスク: 2（上げた後のレビューで通った割合 50%）", out), out
    assert "R1 autopilot-implementer→autopilot-implementer-high（実装役の失敗）" in out


def test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body():
    import sys
    sys.path.insert(0, str(AGENTS.parent / "scripts"))
    import ladder
    for role, rungs in ladder.RUNGS.items():
        base = None
        for _, (agent, model, effort) in rungs.items():
            text = (AGENTS / f"{agent}.md").read_text(encoding="utf-8")
            head, body = text.split("\n---\n", 1)
            assert f"\nmodel: {model}\n" in head + "\n", agent
            assert f"\neffort: {effort}\n" in head + "\n", agent
            base = base or body
            assert body == base, agent


def test_park_names_only_the_requirement_past_the_top_and_the_rest_goes_on(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1, R2]\n")
    raise_rounds(repo, d, 6, "R1")
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 1 and "R1 を park" in r.stdout and "R2" not in r.stdout
    assert night(repo, "park", str(d), "--kind", "other", "--req", "R1", "--op", "R1 の実装",
                 "--reason", "一番上でも通らない").returncode == 0
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "autopilot-implementer"  # R2 の段で渡す


def test_a_fable_pass_does_not_block_the_next_fix_of_the_same_task(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    raise_rounds(repo, d, 5)
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0  # Fable
    run(repo, "review", str(d), "--high", "none")  # 通った
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0 and "fable" in r.stdout


@pytest.mark.parametrize("row", ["- 実装: opus xhigh", "- 実装： opus-xhigh", "* 実装: opus-xhigh", "実装は opus-xhigh にする",
                                 "- 実装: opus-xhigh\n- 実装: fable"])
def test_lint_refuses_a_model_row_it_cannot_read(repo, row):
    d = init_spec(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + f"\n## モデル\n\n{row}\n", encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode != 0 and "モデル" in r.stdout


def test_a_model_row_inside_a_comment_does_not_count_and_a_trailing_comment_is_fine(repo):
    d = init_spec(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8")
                    + "\n## モデル\n\n<!--\n- 評価: fable\n-->\n- 実装: opus-medium <!-- 認証に触る -->\n", encoding="utf-8")
    (d / "tasks.md").write_text("# タスク\n\n- [ ] T1: 規則 [R1]\n", encoding="utf-8")
    assert name(agent_of(repo, d, "review")) == "autopilot-reviewer"
    assert name(agent_of(repo, d, "impl", "T1")) == "autopilot-implementer-opus"
    r = run(repo, "lint", str(d))
    assert "Traceback" not in r.stderr and not re.search(r"ERROR.*モデル", r.stdout)


def test_a_task_whose_only_requirement_is_parked_past_the_top_is_not_handed_out(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    raise_rounds(repo, d, 6, "R1")
    assert night(repo, "park", str(d), "--kind", "other", "--req", "R1", "--op", "R1 の実装",
                 "--reason", "一番上でも通らない").returncode == 0
    for cmd in (["dispatch"], ["agent", "--role", "impl"]):
        r = night(repo, *cmd, str(d), "--task", "T1")
        assert r.returncode == 1 and "autopilot-implementer" not in r.stdout, r.stdout


@pytest.mark.parametrize("line", ["- [X] T1: 規則 [R1]", "- [x] T1: 規則 [R1]　"])
def test_a_task_line_that_check_accepts_is_read_the_same_by_the_ladder(repo, line):
    d = done_spec(repo, line + "\n")
    raise_rounds(repo, d, 6, "R1")
    for cmd in (["dispatch"], ["agent", "--role", "impl"]):
        r = night(repo, *cmd, str(d), "--task", "T1")
        assert r.returncode == 1 and "R1 を park" in r.stdout, r.stdout


def test_a_task_not_in_tasks_md_is_refused(repo):
    d = done_spec(repo, "- [x] T1: 規則 [R1]\n")
    for cmd in (["dispatch"], ["agent", "--role", "impl"]):
        r = night(repo, *cmd, str(d), "--task", "T9")
        assert r.returncode == 1 and "tasks.md に無い" in r.stdout, r.stdout
