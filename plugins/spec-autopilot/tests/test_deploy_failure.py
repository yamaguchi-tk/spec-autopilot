"""デプロイの失敗を拾う（デプロイ後の要件が無い「マージ・デプロイ・QA まで」の spec も、最後のマージのデプロイを確かめる）。"""
from test_autopilot import init_spec, make_done, repo, run, user_says  # noqa: F401
import time

from test_overnight import FULL, checks, ci_await, deploy_ok, full_spec, gh, git_head, merged_pr, night, scoped  # noqa: F401


def local_spec(repo):
    """要件が全部手元で確かめられる（デプロイ後の要件が無い）、範囲が「マージ・デプロイ・QA まで」の spec。"""
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL), encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    return d


def merge(repo, gh, d, sha="m1"):
    gh.answers("pr view", [merged_pr(git_head(repo), sha)])
    r = night(repo, "merged", str(d), "--pr", "7")
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_accepts_a_parked_deploy_without_deployed_requirements(repo, gh):
    d = local_spec(repo)
    merge(repo, gh, d)
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "差分の外").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout


def test_a_parked_failed_deploy_needs_a_smoke_and_the_report_tells_it(repo, gh, tmp_path):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "差分の外").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout, r.stdout
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "デプロイが失敗したまま" in line, line
    time.sleep(0.02)
    ev = tmp_path / "smoke.txt"
    ev.write_text("checked the unchanged behaviour in production\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "fail").returncode == 0
    assert run(repo, "check", str(d)).returncode == 0  # fail でも戻さずに積む
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "デプロイが失敗したまま" in line and "smoke: fail" in line, line


def test_check_rejects_a_failed_deploy_of_the_last_merge(repo, gh):
    d = local_spec(repo)
    merge(repo, gh, d)
    gh.answers("run list", [{"out": [{"databaseId": 5, "workflowName": "deploy", "status": "completed",
                                      "conclusion": "failure"}]}])
    gh.answers("run view", [{"out": {"attempt": 2}}])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 1
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイ" in r.stdout


def deploy(repo, gh, d, pr, sha, conclusion):
    """PR <pr> をマージ（commit <sha>）し、そのデプロイの結果を await で記録する。failure は 2 回目の実行（flake でない）。"""
    gh.answers("pr view", [merged_pr(git_head(repo), sha)])
    assert night(repo, "merged", str(d), "--pr", str(pr)).returncode == 0
    gh.answers("run list", [{"out": [{"databaseId": pr, "workflowName": "deploy", "status": "completed",
                                      "conclusion": conclusion}]}])
    gh.answers("run view", [{"out": {"attempt": 2}}])
    night(repo, "await", str(d), "--kind", "deploy", "--interval", "0")


def ready(repo, gh, d):
    """次の直しの PR（評価役が見た head・CI が通った）を ready に掛ける。"""
    head = git_head(repo)
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head}}])
    gh.answers("pr checks", [checks("pass")])
    assert ci_await(repo, d).returncode == 0
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head}}])
    return night(repo, "ready", str(d), "--pr", "7")


def test_ready_refuses_the_next_fix_after_two_fixes_failed_to_deploy(repo, gh):
    d = local_spec(repo)
    for n in (1, 2):
        deploy(repo, gh, d, n, f"m{n}", "failure")
    assert ready(repo, gh, d).returncode == 0  # 直しはまだ 1 回（2 本目の直しまでは通る）
    deploy(repo, gh, d, 3, "m3", "failure")
    r = ready(repo, gh, d)
    assert r.returncode == 1 and "park --kind deploy" in r.stdout, r.stdout
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "上限" in r.stdout and "park --kind deploy" in r.stdout, r.stdout


def test_a_successful_deploy_starts_the_count_again(repo, gh):
    d = local_spec(repo)
    for n, c in ((1, "failure"), (2, "failure"), (3, "success"), (4, "failure"), (5, "failure")):
        deploy(repo, gh, d, n, f"m{n}", c)
    assert ready(repo, gh, d).returncode == 0


def test_the_same_merge_failing_twice_counts_once(repo, gh):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    deploy(repo, gh, d, 1, "m1", "failure")  # 同じマージのデプロイを待ち直した
    deploy(repo, gh, d, 2, "m2", "failure")
    assert ready(repo, gh, d).returncode == 0


def test_a_merge_without_a_deploy_record_does_not_start_the_count_again(repo, gh):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    deploy(repo, gh, d, 2, "m2", "failure")
    gh.answers("pr view", [merged_pr(git_head(repo), "m3")])
    assert night(repo, "merged", str(d), "--pr", "3").returncode == 0  # await を打ち忘れた
    deploy(repo, gh, d, 4, "m4", "failure")
    assert ready(repo, gh, d).returncode == 1


def test_a_first_attempt_flake_is_not_counted_as_a_failed_fix(repo, gh):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    deploy(repo, gh, d, 2, "m2", "failure")
    gh.answers("pr view", [merged_pr(git_head(repo), "m3")])
    assert night(repo, "merged", str(d), "--pr", "3").returncode == 0
    gh.answers("run list", [{"out": [{"databaseId": 3, "workflowName": "deploy", "status": "completed", "conclusion": "failure"}]}])
    gh.answers("run view", [{"out": {"attempt": 1}}, {"out": "The runner has received a shutdown signal"}])  # 1 回目の実行の flake
    night(repo, "await", str(d), "--kind", "deploy", "--interval", "0")
    assert ready(repo, gh, d).returncode == 0


def test_lint_requires_the_deploy_check_without_deployed_requirements(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL, **{"デプロイの確かめ": ""}), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "デプロイの確かめ" in r.stdout


def test_the_morning_report_tells_a_failed_deploy_without_deployed_requirements(repo, gh):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "デプロイが失敗したまま" in line and "確かめていない" in line, line
    deploy(repo, gh, d, 2, "m2", "success")
    line = night(repo, "report", str(d)).stdout.splitlines()[1]
    assert "デプロイした" in line, line


def test_a_command_start_without_deployed_requirements_is_done_at_the_merge(repo, gh):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL, **{"デプロイの起動": "コマンド: make deploy", "デプロイの確かめ": ""}),
                               encoding="utf-8")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    make_done(repo, d)
    merge(repo, gh, d)
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout  # 夜の間にデプロイのコマンドを新しく打たない
    assert "この夜はデプロイしていない" in night(repo, "report", str(d)).stdout.splitlines()[1]


def capped_with_deployed_requirements(repo, gh, tmp_path, smoke):
    d = full_spec(repo)
    make_done(repo, d)
    for n in (1, 2, 3):
        deploy(repo, gh, d, n, f"m{n}", "failure")
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "直しの上限").returncode == 0
    time.sleep(0.02)
    ev = tmp_path / "smoke.txt"
    ev.write_text("checked the unchanged behaviour in production\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", smoke).returncode == 0
    return run(repo, "check", str(d))


def test_a_capped_deploy_with_deployed_requirements_is_parked_without_a_rollback_when_the_smoke_passes(repo, gh, tmp_path):
    r = capped_with_deployed_requirements(repo, gh, tmp_path, "pass")
    assert "smoke" not in r.stdout and "ロールバック" not in r.stdout, r.stdout


def test_a_capped_deploy_with_deployed_requirements_still_rolls_back_when_the_smoke_fails(repo, gh, tmp_path):
    r = capped_with_deployed_requirements(repo, gh, tmp_path, "fail")
    assert r.returncode == 1 and "ロールバック" in r.stdout, r.stdout


def test_a_capped_park_after_a_rollback_whose_deploy_failed_does_not_restore_production(repo, gh, tmp_path):
    from test_rollback import broken, rollback_pr, smoke
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)  # 最初のマージのデプロイは通り、smoke が落ちた
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた").returncode == 0
    gh.answers("run list", [{"out": [{"databaseId": 8, "workflowName": "deploy", "status": "completed", "conclusion": "failure"}]}])
    night(repo, "await", str(d), "--kind", "deploy", "--interval", "0")
    deploy(repo, gh, d, 9, "m9", "failure")
    deploy(repo, gh, d, 10, "m10", "failure")  # 壊れた後の 3 本とも落ちて上限に当たる（本番は壊れた最初のマージのまま）
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "直しの上限").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "smoke2.txt").returncode == 0
    assert "確かめた" not in night(repo, "report", str(d)).stdout.splitlines()[1]
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout, r.stdout


def test_the_deploy_wait_does_not_take_a_success_of_a_workflow_the_spec_did_not_name(repo, gh):
    d = local_spec(repo)
    merge(repo, gh, d)
    gh.answers("run list", [{"out": [{"databaseId": 5, "workflowName": "ci", "status": "completed", "conclusion": "success"}]}])
    r = night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0")
    assert r.returncode == 2, r.stdout + r.stderr  # 宣言した deploy の run がまだ無い
    r = night(repo, "await", str(d), "--kind", "deploy", "--workflow", "ci", "--interval", "0", "--timeout-min", "0")
    assert r.returncode != 0 and "デプロイの確かめ" in r.stdout + r.stderr
    log = (d / "awaits.jsonl").read_text(encoding="utf-8")
    assert '"result": "success"' not in log, log  # ci の success をデプロイの成功として記録しない（timeout は朝の報告に出す）


def record_smoke(repo, d, tmp_path, value):
    time.sleep(0.02)
    ev = tmp_path / f"smoke-{value}.txt"
    ev.write_text("checked the unchanged behaviour in production\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", value).returncode == 0


def test_a_deploy_that_failed_and_was_fixed_still_needs_a_smoke(repo, gh, tmp_path):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    deploy(repo, gh, d, 2, "m2", "success")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout, r.stdout
    record_smoke(repo, d, tmp_path, "pass")
    assert run(repo, "check", str(d)).returncode == 0
    assert "smoke: pass" in night(repo, "report", str(d)).stdout.splitlines()[1]


def test_a_failed_deploy_followed_by_a_timed_out_fix_still_needs_a_smoke(repo, gh, tmp_path):
    d = local_spec(repo)
    deploy(repo, gh, d, 1, "m1", "failure")
    gh.answers("pr view", [merged_pr(git_head(repo), "m2")])
    assert night(repo, "merged", str(d), "--pr", "2").returncode == 0
    gh.answers("run list", [{"out": []}])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0").returncode == 2
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout, r.stdout
