"""デプロイの workflow が無い repo の「マージ・デプロイ・QA まで」: `- デプロイの起動: なし（マージした commit で QA）` の spec は、
最後のマージの記録（overnight.py merged）を QA の起点にして、デプロイを待たずにマージの後の QA へ進む。合意ありと軽量フローの両方。"""
import json
import time

from test_autopilot import GOOD_SPEC, init_spec, make_done, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_light import light
from test_overnight import FULL, deployed, git_head, gh, merged_pr, night, scoped  # noqa: F401（gh は fixture）

NO_DEPLOY = "なし（マージした commit で QA）"
ROWS = {"QA の環境": "マージした commit の checkout", "QA の書き込み先": "なし",
        "デプロイの起動": NO_DEPLOY, "デプロイの確かめ": ""}


def spec_text(**rows):
    return deployed(scoped(FULL, **{**ROWS, **rows}))


def agreed(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(spec_text(), encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def light_run(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(spec_text(), encoding="utf-8")
    r = light(repo, "approve", str(d), "--source", "依頼文の要約")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def evidence(tmp_path, name="qa.txt"):
    time.sleep(0.02)
    f = tmp_path / name
    f.write_text("$ run the merged commit\nR2 confirmed on the merged commit\n", encoding="utf-8")
    return f


def merge_then_qa(repo, gh, tmp_path, d):
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "overnight.py qa" in r.stdout
    assert "--kind deploy" not in r.stdout and "デプロイを待ち" not in r.stdout  # デプロイを待てとは言わない
    r = night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path)), "--smoke", "pass")
    assert r.returncode == 0, r.stdout + r.stderr
    (d / "evidence" / "R2.txt").write_text("- commit: m1\n- 結果: Confirmed\n$ run the merged commit\nR2 ok\n", encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout


def test_lint_accepts_no_deploy_with_an_empty_deploy_check(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(spec_text(), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout


def test_lint_rejects_no_deploy_with_a_deploy_workflow(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(spec_text(**{"デプロイの確かめ": "deploy"}), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "デプロイの確かめ" in r.stdout


def test_agreed_run_goes_from_the_merge_to_qa_without_a_deploy(repo, gh, tmp_path):
    merge_then_qa(repo, gh, tmp_path, agreed(repo))


def test_light_run_goes_from_the_merge_to_qa_without_a_deploy(repo, gh, tmp_path):
    d = light_run(repo)
    assert state(d)["light"] is True
    merge_then_qa(repo, gh, tmp_path, d)


def test_qa_refuses_evidence_from_before_the_merge(repo, gh, tmp_path):
    d = agreed(repo)
    make_done(repo, d)
    old = evidence(tmp_path, "old.txt")
    time.sleep(0.02)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert night(repo, "qa", str(d), "--evidence", str(old), "--smoke", "pass").returncode != 0


def test_qa_without_a_merge_is_refused(repo, tmp_path):
    d = agreed(repo)
    assert night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path)), "--smoke", "pass").returncode != 0


def test_smoke_after_the_merge_confirms_production(repo, gh, tmp_path):
    import overnight
    from pathlib import Path
    d = agreed(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert overnight.production(Path(d), state(d)) == overnight.UNKNOWN
    assert night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path)), "--smoke", "pass").returncode == 0
    assert overnight.production(Path(d), state(d)) == overnight.CONFIRMED
    s = state(d)
    s["qa_runs"].append({"evidence": "x", "mtime": 0, "smoke": "fail", "at": time.time()})
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert overnight.production(Path(d), state(d)) == overnight.BROKEN


def broken_without_deploy(repo, gh, tmp_path, d):
    """マージの記録を起点に smoke が落ちた状態にする。マージの sha を返す。"""
    from test_rollback import base_commit
    base_commit(repo)
    make_done(repo, d)
    sha = git_head(repo)
    gh.answers("pr view", [merged_pr(sha, sha)])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path, "fail.txt")), "--smoke", "fail").returncode == 0
    return sha


import pytest  # noqa: E402


@pytest.mark.parametrize("start", [agreed, light_run])
def test_a_revert_merge_restores_production_without_a_deploy(repo, gh, tmp_path, start):
    from test_rollback import rollback_pr
    d = start(repo)
    sha = broken_without_deploy(repo, gh, tmp_path, d)
    head = rollback_pr(repo, gh, sha)
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 0, r.stdout + r.stderr
    gh.answers("pr view", [merged_pr(head, head)])
    r = night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイを待ち" not in r.stdout  # 待つデプロイは無い
    assert night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path, "smoke2.txt")), "--smoke", "pass").returncode == 0
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "戻した。直しは朝に", "--evidence", "smoke2.txt")
    assert r.returncode == 0, r.stdout + r.stderr  # 戻して確かめたので、戻せない理由なしで block できる
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "本番: 戻して確かめた" in line and "デプロイは無い" in line


def test_the_report_says_production_is_the_merged_commit(repo, gh, tmp_path):
    d = agreed(repo)
    merge_then_qa(repo, gh, tmp_path, d)
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "本番: 確かめた" in line and "デプロイは無い" in line


def test_a_passing_smoke_without_a_merge_leaves_production_broken(repo, gh, tmp_path):
    import overnight
    from pathlib import Path
    d = agreed(repo)
    broken_without_deploy(repo, gh, tmp_path, d)
    assert night(repo, "qa", str(d), "--evidence", str(evidence(tmp_path, "again.txt")), "--smoke", "pass").returncode == 0
    assert overnight.production(Path(d), state(d)) == overnight.BROKEN  # 抜けるのは壊れた後のマージだけ
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "x", "--evidence", "again.txt")
    assert r.returncode != 0 and "本番が良くない" in r.stderr
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": git_head(repo)}}])
    r = night(repo, "ready", str(d), "--pr", "8")
    assert r.returncode == 1 and "戻す PR でなければマージしない" in r.stdout  # 戻す PR でない直しは通さない
