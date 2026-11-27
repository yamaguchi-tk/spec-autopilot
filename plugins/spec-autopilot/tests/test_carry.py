"""承認し直しのとき、コードが同じならマージとデプロイの記録を持ち越す仕組み（scripts/carry.py）を、入口（CLI）から確かめる。
gh は test_overnight.py の偽物で答える。"""
import json
import subprocess
import sys
import time

import pytest

from test_autopilot import PLUGIN, make_done, real_run, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_lineup import line
from test_overnight import GIT, deploy_ok, full_spec, gh, git_head, merged_pr, night  # noqa: F401

sys.path.insert(0, str(PLUGIN / "scripts"))
import carry  # noqa: E402
import deploy  # noqa: E402

NOT_CARRIED = "持ち越さなかった"
CONTAINS = "今の HEAD を含むマージ"


def merged_and_deployed(repo, gh, d, pr="7"):
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", pr).returncode == 0
    gh.answers("run list", [deploy_ok()])
    r = night(repo, "await", str(d), "--kind", "deploy", "--interval", "0")
    assert r.returncode == 0, r.stdout + r.stderr


def block(repo, d):
    time.sleep(0.02)
    r = run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y", "--no-rollback", "本番を確かめていない")
    assert r.returncode == 0, r.stdout + r.stderr


def commit(repo, *paths, msg="c"):
    subprocess.run(["git", "add", "-f", "--", *paths], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", msg], cwd=repo, check=True)


def fix_the_words(repo, d, old="その列を消す。", new="その列を消す（文を直した）。"):
    """要件の文だけを直して commit する（docs/specs の中だけの差分）。"""
    p = d / "spec.md"
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    commit(repo, str(p.relative_to(repo)), msg="spec words")


def reapprove(repo, d, *extra):
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK", *extra)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def blocked_after_deploy(repo, gh):
    d = full_spec(repo)
    merged_and_deployed(repo, gh, d)
    block(repo, d)
    return d


def test_reapproval_after_a_words_only_fix_carries_the_merge_and_the_deploy(repo, gh):
    d = blocked_after_deploy(repo, gh)
    before = state(d)
    fix_the_words(repo, d)
    r = reapprove(repo, d)
    s = state(d)
    assert "持ち越した: マージ 1 件（PR 7）" in r.stdout
    assert s["merges"] == before["merges"] and s["history"][-1]["merges"] == before["merges"]
    assert s["merged_at"] == s["approved_at"] and s["paused_at_merge"] == 0 and s["awaits_since"] == before["approved_at"]
    assert [a["kind"] for a in deploy.awaits(d, s) if a.get("result") == "success"] == ["deploy"]
    assert deploy.deploys_of_last_merge(d, s)


def test_a_carried_round_counts_reviews_qa_and_dispatches_again(repo, gh):
    d = blocked_after_deploy(repo, gh)
    assert state(d)["dispatches"] and state(d)["reviews"] and state(d)["handoffs"]
    fix_the_words(repo, d)
    reapprove(repo, d)
    s = state(d)
    assert s["reviews"] == [] and s["fails"] == {} and s["streak"] == {} and s["reworks"] == {}
    for k in ("qa_runs", "parked", "lenses", "rolled_back"):
        assert not s.get(k), k
    assert len(s["dispatches"]) == 1 and len(s["handoffs"]) == 1  # 閉じた dispatch と handoff は持ち越す（spec の外が同じ）
    assert s["history"][-1]["dispatches"] and s["history"][-1]["handoffs"]  # 前の巡は今までどおり history にも写す


def test_check_counts_a_carried_merge_while_only_docs_changed_and_asks_again_after_a_code_change(repo, gh):
    d = blocked_after_deploy(repo, gh)
    fix_the_words(repo, d)
    reapprove(repo, d)
    assert CONTAINS not in run(repo, "check", str(d)).stdout
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    commit(repo, "fix.js", msg="code after the carry")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and CONTAINS in r.stdout


def test_check_of_a_spec_that_carried_nothing_still_asks_for_the_merge_after_a_spec_only_commit(repo, gh):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert CONTAINS not in run(repo, "check", str(d)).stdout
    fix_the_words(repo, d)
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and CONTAINS in r.stdout


def edit_state(d, fn):
    s = state(d)
    fn(s)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")


def spoil_code(repo, d):
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    commit(repo, "fix.js")


def spoil_rollback(repo, d):
    edit_state(d, lambda s: s["merges"][-1].update(rollback=True))


def spoil_rolled_back_by_command(repo, d):
    edit_state(d, lambda s: s.update(rolled_back=[{"reason": "smoke が落ちた", "evidence": "e", "mtime": 1.0, "at": time.time()}]))


def spoil_head(repo, d):
    edit_state(d, lambda s: s["merges"][-1].pop("head"))


def spoil_unknown_head(repo, d):
    edit_state(d, lambda s: s["merges"][-1].update(head="0" * 40))


def spoil_approved_at(repo, d):
    edit_state(d, lambda s: s.update(approved_at=None))


@pytest.mark.parametrize("spoil", [spoil_code, spoil_rollback, spoil_rolled_back_by_command, spoil_head, spoil_unknown_head, spoil_approved_at])
def test_reapproval_carries_nothing_when_the_code_differs_or_cannot_be_decided(repo, gh, spoil):
    d = blocked_after_deploy(repo, gh)
    fix_the_words(repo, d)
    spoil(repo, d)
    r = reapprove(repo, d)
    s = state(d)
    assert not s.get("merges") and s.get("merged_at") is None and "awaits_since" not in s
    assert NOT_CARRIED in r.stdout and "持ち越した" not in r.stdout
    assert deploy.awaits(d, s) == [] and s["history"][-1].get("merges")


def test_a_spec_without_a_merge_prints_nothing_about_carrying(repo):
    d = full_spec(repo)
    make_done(repo, d)
    block(repo, d)
    r = reapprove(repo, d)
    assert "持ち越" not in r.stdout and not state(d).get("merges")


CARRIED_DISPATCH = "dispatch を引き継いだ: "
NOT_CARRIED_DISPATCH = "dispatch を引き継がなかった: "


def blocked_after_handoff(repo):
    """dispatch → 実装の commit → handoff → review まで進んで blocked にした spec（マージの記録は無い）。"""
    d = full_spec(repo)
    make_done(repo, d)
    block(repo, d)
    return d


def test_reapproval_after_a_words_only_fix_carries_the_closed_dispatch_and_handoff_and_review_passes_without_a_new_dispatch(repo):
    d = blocked_after_handoff(repo)
    fix_the_words(repo, d)
    r = reapprove(repo, d)
    out = [x for x in r.stdout.splitlines() if x.startswith(CARRIED_DISPATCH)]
    assert len(out) == 1 and "T1" in out[0] and f"overnight.py handoff {d} --task T1" in out[0], r.stdout
    assert NOT_CARRIED_DISPATCH not in r.stdout and "持ち越" not in r.stdout
    s = state(d)
    assert len(s["dispatches"]) == 1 and len(s["handoffs"]) == 1 and "prototype" not in s["dispatches"][0]
    h = night(repo, "handoff", str(d), "--task", "T1")  # dispatch は打たない
    assert h.returncode == 0, h.stdout + h.stderr
    assert len(state(d)["dispatches"]) == 1 and len(state(d)["handoffs"]) == 2
    for rid in ("R1", "R2"):
        real_run(repo, d, rid)
    v = run(repo, "review", str(d), "--high", "none")
    assert v.returncode == 0, v.stdout + v.stderr


def test_reapproval_does_not_carry_the_dispatch_when_a_file_outside_the_spec_changed_and_handoff_is_refused_without_a_dispatch(repo):
    d = blocked_after_handoff(repo)
    fix_the_words(repo, d)
    spoil_code(repo, d)
    r = reapprove(repo, d)
    assert NOT_CARRIED_DISPATCH in r.stdout and CARRIED_DISPATCH not in r.stdout
    s = state(d)
    assert not s.get("dispatches") and not s.get("handoffs") and s["history"][-1]["dispatches"]
    h = night(repo, "handoff", str(d), "--task", "T1")
    assert h.returncode != 0 and "dispatch の記録が無い" in h.stdout + h.stderr


def test_reapproval_does_not_carry_a_dispatch_that_no_handoff_closed(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("# タスク\n\n- [ ] T1: 規則のモジュール [R1, R2]\n", encoding="utf-8")
    r = night(repo, "dispatch", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    block(repo, d)
    fix_the_words(repo, d)
    r = reapprove(repo, d)
    assert NOT_CARRIED_DISPATCH in r.stdout and "閉じていない" in r.stdout and CARRIED_DISPATCH not in r.stdout
    assert not state(d).get("dispatches")
    assert night(repo, "handoff", str(d), "--task", "T1").returncode != 0


def test_reapproval_of_a_spec_without_a_dispatch_says_why_it_carried_no_dispatch(repo):
    d = full_spec(repo)
    block(repo, d)
    r = reapprove(repo, d)
    assert f"{NOT_CARRIED_DISPATCH}前の巡に dispatch が無い" in r.stdout and CARRIED_DISPATCH not in r.stdout
    assert not state(d).get("dispatches")


def test_queued_reapproval_carries_the_dispatch_when_lineup_next_starts_it(repo):
    d = blocked_after_handoff(repo)
    fix_the_words(repo, d)
    r = reapprove(repo, d, "--queue")
    assert CARRIED_DISPATCH not in r.stdout and state(d)["phase"] == "queued"
    r = line(repo, "next")
    assert r.returncode == 0 and CARRIED_DISPATCH in r.stdout and "--task T1" in r.stdout, r.stdout + r.stderr
    s = state(d)
    assert s["phase"] == "building" and len(s["dispatches"]) == 1 and len(s["handoffs"]) == 1
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0


@pytest.mark.parametrize("prev", ["done", "building", "queued"])
def test_only_a_blocked_spec_carries_the_dispatch(repo, prev):
    s = {"dispatches": [{"tasks": ["T1"]}], "handoffs": [{"dispatch": 0, "tip": git_head(repo)}]}
    assert carry.dispatch_plan(repo, "d", s, prev) == (False, None)


def test_a_second_reapproval_keeps_the_first_start_of_the_carried_records(repo, gh):
    d = blocked_after_deploy(repo, gh)
    since = state(d)["approved_at"]
    fix_the_words(repo, d)
    reapprove(repo, d)
    block(repo, d)
    fix_the_words(repo, d, "（文を直した）", "（もう一度直した）")
    r = reapprove(repo, d)
    s = state(d)
    assert "持ち越した" in r.stdout and s["awaits_since"] == since and deploy.deploys_of_last_merge(d, s)


def test_queued_reapproval_carries_when_lineup_next_starts_it(repo, gh):
    d = blocked_after_deploy(repo, gh)
    fix_the_words(repo, d)
    reapprove(repo, d, "--queue")
    assert state(d)["phase"] == "queued" and state(d)["merges"]
    r = line(repo, "next")
    assert r.returncode == 0 and "持ち越した: マージ 1 件（PR 7）" in r.stdout, r.stdout + r.stderr
    s = state(d)
    assert s["phase"] == "building" and s["merges"] and s["merged_at"] == s["approved_at"]


@pytest.mark.parametrize("prev", ["done", "building"])
def test_only_a_blocked_spec_carries(repo, prev):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)
    merges = [{"pr": 7, "sha": "m1", "head": git_head(repo)}]
    kept, note = carry.plan(repo, {"merges": merges, "approved_at": 1.0}, prev)
    assert not kept and note.startswith(NOT_CARRIED)


def timed_out_await(repo, gh, d, kind):
    """前の巡で、マージの後に待ちが上限（0 分）を過ぎて終わった記録を作る。"""
    if kind == "deploy":
        gh.answers("run list", [{"out": [{"databaseId": 5, "workflowName": "deploy", "status": "in_progress", "conclusion": None}]}])
        r = night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0")
    else:
        gh.answers("pr view", [{"out": {"reviewDecision": "REVIEW_REQUIRED", "headRefOid": "h8"}}])
        r = night(repo, "await", str(d), "--kind", "review", "--pr", "8", "--interval", "0", "--timeout-min", "0")
    assert r.returncode == 2, r.stdout + r.stderr


def merged_then_timed_out_then_carried(repo, gh, kind):
    d = full_spec(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    timed_out_await(repo, gh, d, kind)
    block(repo, d)
    fix_the_words(repo, d)
    reapprove(repo, d)
    return d


def test_a_carried_round_does_not_count_the_deploy_timeout_of_the_earlier_round_as_parked(repo, gh):
    d = merged_then_timed_out_then_carried(repo, gh, "deploy")
    s = state(d)
    assert s["merges"] and s["awaits_since"]
    assert deploy.parked_ops(d, s) == []
    assert "deploy" not in deploy.exempt_kinds(d, s)


def test_a_carried_round_does_not_exempt_the_merge_by_a_review_timeout_of_the_earlier_round(repo, gh):
    d = merged_then_timed_out_then_carried(repo, gh, "review")
    s = state(d)
    assert deploy.parked_ops(d, s) == []
    assert "merge" not in deploy.exempt_kinds(d, s)


def test_a_carried_round_keeps_the_deploy_success_of_the_earlier_round_and_parks_nothing(repo, gh):
    d = blocked_after_deploy(repo, gh)
    fix_the_words(repo, d)
    reapprove(repo, d)
    s = state(d)
    assert deploy.parked_ops(d, s) == [] and deploy.deploys_of_last_merge(d, s)


def test_check_asks_for_the_merge_containing_head_after_a_code_change_even_if_the_earlier_round_timed_out_in_review(repo, gh):
    d = merged_then_timed_out_then_carried(repo, gh, "review")
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    commit(repo, "fix.js", msg="code after the carry")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and CONTAINS in r.stdout


def test_check_asks_for_the_merge_containing_head_after_a_code_change_when_the_earlier_round_had_no_timeout(repo, gh):
    d = blocked_after_deploy(repo, gh)
    fix_the_words(repo, d)
    reapprove(repo, d)
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    commit(repo, "fix.js", msg="code after the carry")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and CONTAINS in r.stdout
