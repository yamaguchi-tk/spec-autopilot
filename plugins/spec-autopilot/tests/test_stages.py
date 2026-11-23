"""QA の方向性の段（手元で実物・デプロイ後・代役）と、段ごとの証拠の要求を、入口（CLI）から確かめる。"""
import json
import time

import pytest

from test_autopilot import GOOD_SPEC, hand_off, init_spec, make_done, real_run, repo, run, state, user_says  # noqa: F401（repo は fixture）
from test_overnight import FULL, checks, deploy_ok, gh, git_head, merged_pr, night, scoped  # noqa: F401（gh は fixture）

R2_ROW = "| R2 | 手元で実物 | ブラウザで操作 | 再開後に盤面が空になる |"


def with_r2(spec, stage, *lines):
    return spec.replace(R2_ROW, R2_ROW.replace("手元で実物", stage) + ("\n\n" + "\n".join(lines) if lines else ""))


def lint(repo, text):
    d = init_spec(repo, f"s{len(list((repo / 'docs' / 'specs').glob('*'))) if (repo / 'docs' / 'specs').exists() else 0}")
    (d / "spec.md").write_text(text, encoding="utf-8")
    return run(repo, "lint", str(d))


def approve(repo, text):
    d = init_spec(repo)
    (d / "spec.md").write_text(text, encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


# --- lint ---

@pytest.mark.parametrize("stage", ["", "単体", "本番"])
def test_lint_rejects_a_row_without_a_known_stage(repo, stage):
    r = lint(repo, with_r2(GOOD_SPEC, stage))
    assert r.returncode == 1 and "段" in r.stdout


def test_lint_requires_the_reason_for_a_deploy_stage(repo):
    r = lint(repo, with_r2(scoped(FULL), "デプロイ後"))
    assert r.returncode == 1 and "手元でできない理由" in r.stdout
    r = lint(repo, with_r2(scoped(FULL), "デプロイ後", "- 手元でできない理由: R2（bot をローカルで起動できない）"))
    assert r.returncode == 0, r.stdout


def test_lint_requires_the_reason_for_a_stand_in(repo):
    r = lint(repo, with_r2(GOOD_SPEC, "代役"))
    assert r.returncode == 1 and "代役の理由" in r.stdout
    assert lint(repo, with_r2(GOOD_SPEC, "代役", "- 代役の理由: R2（実物が手元にもデプロイ後にも無い）")).returncode == 0


def test_lint_rejects_a_reason_for_an_unknown_requirement(repo):
    r = lint(repo, with_r2(GOOD_SPEC, "代役", "- 代役の理由: R2（x）", "- 代役の理由: R9（x）"))
    assert r.returncode == 1 and "R9" in r.stdout


def test_a_full_scope_without_deploy_stages_may_leave_the_qa_and_rollback_rows_empty(repo):
    rows = {"QA の環境": "", "ロールバック": ""}
    assert lint(repo, scoped(FULL, **rows)).returncode == 0
    r = lint(repo, scoped(FULL, **rows, **{"デプロイの起動": ""}))
    assert r.returncode == 1 and "デプロイの起動" in r.stdout  # デプロイの失敗を拾うので、起動は要る
    r = lint(repo, with_r2(scoped(FULL, **rows), "デプロイ後", "- 手元でできない理由: R2（x）"))
    assert r.returncode == 1 and "ロールバック" in r.stdout


# --- check ---

def test_check_requires_the_output_of_a_real_run(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    (d / "evidence" / "R1.txt").unlink()
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "evidence/R1" in r.stdout


def test_check_requires_the_command_line_in_a_real_run_output(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    (d / "evidence" / "R1.txt").write_text("ran and saw the expected output\n", encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R1" in r.stdout and "$ " in r.stdout


def test_a_real_run_output_from_before_a_reapproval_is_refused(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "直して").returncode == 0
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    hand_off(repo, d)
    assert run(repo, "review", str(d), "--high", "none").returncode == 0  # 評価役が R1 の出力を書き直さなかった
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R1" in r.stdout and "commit" in r.stdout


def test_a_real_run_output_from_a_failed_round_is_refused(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    assert run(repo, "review", str(d), "--high", "R1").returncode == 0
    assert run(repo, "review", str(d), "--high", "none").returncode == 0  # main の回し直しで閉じたが、出力を書き直していない
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R1" in r.stdout
    real_run(repo, d, "R1")
    real_run(repo, d, "R2")
    assert run(repo, "check", str(d)).returncode == 0


def test_check_does_not_take_an_empty_output(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    (d / "evidence" / "R1.txt").write_text("", encoding="utf-8")
    assert run(repo, "check", str(d)).returncode == 1


def test_check_requires_an_approved_reason_for_unverified(repo):
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    qa = (d / "qa.md").read_text(encoding="utf-8").replace(
        "| R2 | pass | cmd: playwright でEnterを押し盤面が空になった |", "| R2 | unverified | ブラウザの tool が無い |")
    (d / "qa.md").write_text(qa, encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "unverified の承認" in r.stdout
    assert night(repo, "park", str(d), "--kind", "qa", "--op", "ブラウザで操作", "--reason", "tool が無い",
                 "--req", "R2").returncode == 0
    assert run(repo, "check", str(d)).returncode == 0  # 積んだ要件の unverified は通す（朝の報告に出る）


def test_a_full_scope_without_deploy_stages_is_done_at_the_deploy_without_a_qa(repo, gh):
    d = approve(repo, scoped(FULL))
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイ" in r.stdout  # デプロイの失敗を拾うため、デプロイの成功は待つ
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert run(repo, "check", str(d)).returncode == 0  # 要件が全部手元で確かめられたので、デプロイの後の QA を通らない


def test_a_deploy_stage_needs_an_output_written_after_the_deploy(repo, gh, tmp_path):
    d = approve(repo, with_r2(scoped(FULL), "デプロイ後", "- 手元でできない理由: R2（bot をローカルで起動できない）"))
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    time.sleep(0.02)
    ev = tmp_path / "qa.txt"
    ev.write_text("x\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "pass").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "evidence/R2" in r.stdout  # R2 の出力はデプロイの前のもの
    (d / "evidence" / "R2.txt").write_text("- commit: m1\n- 結果: Confirmed\n$ post #bot-test\nposted to #bot-test after the deploy\n",
                                           encoding="utf-8")
    assert run(repo, "check", str(d)).returncode == 0


# --- 観点ごとの記録 ---

def test_lens_records_counts_and_the_report_shows_them(repo):
    d = approve(repo, scoped("PR まで"))
    r = night(repo, "lens", str(d), "--name", "IaC の初回の apply", "--found", "3", "--reproduced", "2", "--fixed", "2")
    assert r.returncode == 0, r.stderr
    assert state(d)["lenses"][-1] == {"name": "IaC の初回の apply", "found": 3, "reproduced": 2, "fixed": 2,
                                      "at": state(d)["lenses"][-1]["at"]}
    make_done(repo, d)
    assert "IaC の初回の apply" in night(repo, "report", str(d)).stdout


def test_lens_rejects_counts_that_do_not_add_up(repo):
    d = approve(repo, scoped("PR まで"))
    assert night(repo, "lens", str(d), "--name", "x", "--found", "1", "--reproduced", "2", "--fixed", "0").returncode != 0


# --- 検査の時点で分ける・デプロイの記録・宣言の行・承認の正本 ---

DEPLOYED_R2 = ("デプロイ後", "- 手元でできない理由: R2（bot をローカルで起動できない）")


def set_r2(d, result, evidence):
    qa = (d / "qa.md").read_text(encoding="utf-8").replace(
        "| R2 | pass | cmd: playwright でEnterを押し盤面が空になった |", f"| R2 | {result} | {evidence} |")
    (d / "qa.md").write_text(qa, encoding="utf-8")


def test_the_pr_check_takes_a_deploy_stage_that_waits_for_the_deploy(repo):
    d = approve(repo, with_r2(scoped(FULL), *DEPLOYED_R2))
    make_done(repo, d)
    set_r2(d, "unverified", "デプロイ後に確かめる")
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout  # 承認の行も park も無くても、PR の前はデプロイ後の要件を待つ


def test_the_pr_check_refuses_a_deploy_stage_marked_pass_before_the_deploy(repo):
    d = approve(repo, with_r2(scoped(FULL), *DEPLOYED_R2))
    make_done(repo, d)
    (d / "evidence" / "R2.txt").write_text("- commit: x\n- 結果: Confirmed\n$ run\nlocal\n", encoding="utf-8")
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 1 and "R2" in r.stdout


def test_a_deploy_stage_pass_without_a_deploy_record_is_refused(repo, gh):
    d = approve(repo, with_r2(scoped(FULL), *DEPLOYED_R2))
    make_done(repo, d)
    (d / "evidence" / "R2.txt").write_text("- commit: m1\n- 結果: Confirmed\n$ run\nlocal\n", encoding="utf-8")
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "範囲の外").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R2" in r.stdout and "デプロイ" in r.stdout


@pytest.mark.parametrize("body", ["- commit: m1\n- 結果: Inconclusive\n$ curl x\nok\n", "- commit: zz\n- 結果: Confirmed\n$ curl x\nok\n",
                                  "posted\n",
                                  "- commit: m1\n- 結果: Inconclusive\n$ curl x\n観察 2:\n- 結果: Confirmed\n",  # 頭の外の宣言
                                  "- commit: m1\n- 結果: Confirmed\n- 結果: Inconclusive\n$ curl x\nok\n",  # 宣言が 2 本
                                  "$ curl x\n- commit: m1\n- 結果: Confirmed\nok\n",  # 頭に無い
                                  "- commit: m1\n- 結果: Confirmed\nposted to #bot-test\n"])  # 実行したコマンドの行が無い
def test_a_deploy_stage_pass_needs_the_declared_commit_and_confirmed(repo, gh, tmp_path, body):
    d = approve(repo, with_r2(scoped(FULL), *DEPLOYED_R2))
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    time.sleep(0.02)
    ev = tmp_path / "qa.txt"
    ev.write_text("x\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "pass").returncode == 0
    (d / "evidence").mkdir(exist_ok=True)
    (d / "evidence" / "R2.txt").write_text(body, encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R2" in r.stdout


def test_lint_requires_an_approval_line_for_unverified_in_the_criteria(repo):
    text = scoped(FULL).replace("| 再開後に盤面が空になる |", "| unverified（CI で確かめる） |")
    r = lint(repo, text)
    assert r.returncode == 1 and "unverified の承認" in r.stdout
    approved = text.replace("| unverified（CI で確かめる） |", "| unverified（CI で確かめる） |\n\n- unverified の承認: R2（CI で確かめる）")
    r = lint(repo, approved)
    assert r.returncode == 0, r.stdout


def test_lint_requires_an_approval_for_a_deploy_stage_that_the_scope_never_reaches(repo):
    r = lint(repo, with_r2(scoped("マージまで"), *DEPLOYED_R2))
    assert r.returncode == 1 and "unverified の承認" in r.stdout


def test_a_full_scope_without_deploy_stages_still_needs_the_write_target(repo):
    r = lint(repo, scoped(FULL, **{"QA の書き込み先": ""}))
    assert r.returncode == 1 and "QA の書き込み先" in r.stdout


def test_an_old_spec_without_the_stage_column_keeps_the_old_unverified_rule(repo):
    import autopilot
    d = approve(repo, scoped("PR まで"))
    make_done(repo, d)
    spec = (d / "spec.md").read_text(encoding="utf-8")
    old = spec.replace("| 要件 | 段 | 確かめ方 | 合格基準 |", "| 要件 | 確かめ方 | 合格基準 |").replace("|---|---|---|---|", "|---|---|---|")
    old = old.replace("| R1 | 手元で実物 |", "| R1 |").replace("| R2 | 手元で実物 |", "| R2 |")
    (d / "spec.md").write_text(old, encoding="utf-8")
    s = state(d)
    s["spec_sha256"] = autopilot.sha(d)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    set_r2(d, "unverified", "ブラウザの tool が無い")
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout  # 承認したときの規則（理由つきの unverified は通る）のまま


def test_ran_stays_linear_on_command_lines_without_output():
    """Stop hook の時間の上限（30 秒）に収める。`$ ` の行だけが続く形で二乗にならない。"""
    import stages
    text = "- commit: x\n" + "$ a\n" * 20000
    start = time.monotonic()
    assert stages.ran(text) is False
    assert time.monotonic() - start < 2
    assert stages.ran(text + "ok\n") is True


def test_head_rows_stay_linear_on_a_long_run_of_spaces_in_a_value():
    import stages
    text = "- commit: x" + " " * 200000 + "y\n$ a\nok\n"
    start = time.monotonic()
    assert stages.head_rows(text) == [("commit", "x" + " " * 200000 + "y")]
    assert time.monotonic() - start < 2
    assert stages.head_rows("- 結果:  Confirmed \t\n- commit:abc\nx\n- z: 1\n") == [("結果", "Confirmed"), ("commit", "abc")]
