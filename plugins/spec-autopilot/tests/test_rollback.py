"""壊れた本番を朝まで残さない仕組み（本番の状態・smoke・ロールバック）と、夜通しの前提の確認・レビューの承認の待ち・通知を、
入口（CLI と hook）から確かめる。gh と osascript は PATH に置いた偽物で答える。"""
import json
import os
import subprocess
import time

import pytest

from test_autopilot import make_done, repo, run, state, stop_hook, user_says, init_spec  # noqa: F401（repo は fixture）
from test_overnight import (FULL, GIT, checks, deploy_ok, deployed, full_spec, gh, git_head, merged_pr, night,  # noqa: F401
                            scoped)


def base_commit(repo):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)


def merged_and_deployed(repo, gh, d):
    """今の HEAD を最初のマージ（squash の commit とみなす）として記録し、デプロイを通す。マージの sha を返す。"""
    sha = git_head(repo)
    gh.answers("pr view", [merged_pr(sha, sha)])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    return sha


def smoke(repo, d, tmp_path, result, name="smoke.txt"):
    time.sleep(0.02)
    ev = tmp_path / name
    ev.write_text(f"smoke {result}\n", encoding="utf-8")
    return night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", result)


def broken(repo, gh, d, tmp_path):
    base_commit(repo)
    make_done(repo, d)
    sha = merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "fail").returncode == 0
    return sha


# --- smoke と本番の状態 ---

def test_qa_requires_a_known_smoke_result(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "maybe").returncode != 0
    time.sleep(0.02)
    ev = tmp_path / "e.txt"
    ev.write_text("x\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev)).returncode != 0  # --smoke は省けない


@pytest.mark.parametrize("result", ["fail", "unknown"])
def test_a_failed_or_unknown_smoke_leaves_production_broken_and_check_demands_a_rollback(repo, gh, tmp_path, result):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, result).returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout
    out = night(repo, "report", str(d)).stdout
    assert "本番: 壊れたまま" in out.splitlines()[1]


def test_a_failed_deploy_does_not_confirm_production(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    sha = git_head(repo)
    gh.answers("pr view", [merged_pr(sha, sha)])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [{"out": [{"databaseId": 5, "workflowName": "deploy", "status": "completed",
                                      "conclusion": "failure"}]}])
    gh.answers("run view", [{"out": {"attempt": 2}}])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 1
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout
    assert smoke(repo, d, tmp_path, "fail").returncode == 0  # 失敗したデプロイの後の smoke も記録できる


def test_a_passing_smoke_confirms_production(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    sha = merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "pass").returncode == 0
    (d / "evidence" / "R2.txt").write_text(f"- commit: {sha}\n- 結果: Confirmed\n$ post #bot-test\nok\n", encoding="utf-8")
    assert run(repo, "check", str(d)).returncode == 0
    assert "本番: 確かめた" in night(repo, "report", str(d)).stdout


# --- ロールバックの順序と確かめ ---

def rollback_pr(repo, gh, sha, good=True, base=None):
    if good:
        subprocess.run([*GIT, "revert", "--no-edit", sha], cwd=repo, check=True, capture_output=True)
    else:
        (repo / "unrelated.txt").write_text("x\n", encoding="utf-8")
        subprocess.run([*GIT, "add", "unrelated.txt"], cwd=repo, check=True)
        subprocess.run([*GIT, "commit", "-q", "-m", "not a revert"], cwd=repo, check=True)
    head = git_head(repo)
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head}}])
    gh.answers("pr checks", [checks("pass")])
    assert night(repo, "await", str(d_of(repo)), "--kind", "ci", "--pr", "8", "--interval", "0").returncode == 0
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head, "baseRefOid": base or sha}}])
    return head


def d_of(repo):
    return next((repo / "docs" / "specs").iterdir())


def test_ready_refuses_a_fix_while_production_is_broken(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": git_head(repo)}}])
    r = night(repo, "ready", str(d), "--pr", "8")
    assert r.returncode == 1 and "ロールバック" in r.stdout


def test_ready_rollback_takes_only_a_pr_that_restores_the_merged_files(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    rollback_pr(repo, gh, sha, good=False)
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 1 and "戻して" in r.stdout
    subprocess.run([*GIT, "reset", "-q", "--hard", sha], cwd=repo, check=True)
    rollback_pr(repo, gh, sha)
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_confirmed_rollback_ends_the_night_with_production_restored(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    r = night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた")
    assert r.returncode == 0, r.stdout + r.stderr
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout  # 戻したデプロイの後の smoke がまだ無い
    assert smoke(repo, d, tmp_path, "pass", "smoke2.txt").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R2" in r.stdout  # 戻した後はデプロイ後の要件を pass にしない
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "戻した。直しは朝に", "--evidence", "smoke2.txt")
    assert r.returncode == 0, r.stdout + r.stderr  # 戻した夜は、直しを続けないなら block で人に渡す
    out = night(repo, "report", str(d)).stdout
    assert "本番: 戻して確かめた" in out.splitlines()[1] and "smoke が落ちた" in out


def test_merged_rollback_refuses_a_merge_that_does_not_restore(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha, good=False)
    gh.answers("pr view", [merged_pr(head, head)])
    r = night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "x")
    assert r.returncode == 1 and not any(m.get("rollback") for m in state(d)["merges"])


def test_past_the_post_merge_budget_an_unconfirmed_production_demands_a_rollback(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    s = state(d)
    s["merged_at"] = time.time() - (s["post_budget_min"] * 1.5) * 60
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "マージ後の予算" in r.stdout and "ロールバック" in r.stdout


def test_the_stop_hook_keeps_blocking_past_twice_the_budget_while_production_is_broken(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    s = state(d)
    s["merged_at"] = time.time() - (s["post_budget_min"] * 3) * 60
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    out = json.loads(stop_hook(repo).stdout)
    assert out["decision"] == "block" and "ロールバック" in out["reason"]


# --- 夜通しの前提の確認（承認のとき） ---

def aws_home(tmp_path, monkeypatch, expires_in_min, refresh=False):
    home = tmp_path / "home"
    (home / ".aws" / "sso" / "cache").mkdir(parents=True)
    (home / ".aws" / "config").write_text(
        "[profile dev]\nsso_session = corp\n\n[sso-session corp]\nsso_start_url = https://corp.awsapps.com/start\n",
        encoding="utf-8")
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in_min * 60))
    (home / ".aws" / "sso" / "cache" / "t.json").write_text(json.dumps(
        {"startUrl": "https://corp.awsapps.com/start", "expiresAt": expires, **({"refreshToken": "***"} if refresh else {})}),
        encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))


def gdd_on(repo, value=True, where="user"):
    """Claude Code の設定で GDD の plugin を有効（value）にする。where は user・project・local。"""
    f = {"user": repo.parent / ".claude-config" / "settings.json",
         "project": repo / ".claude" / "settings.json",
         "local": repo / ".claude" / "settings.local.json"}[where]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"enabledPlugins": {"gate-driven-development@any-marketplace": value}}), encoding="utf-8")


def gdd_marker(repo, line="active: true"):
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "gdd-dev.local.md").write_text(f"---\n{line}\n---\n", encoding="utf-8")


def approve_text(repo, text):
    d = init_spec(repo)
    (d / "spec.md").write_text(text, encoding="utf-8")
    user_says(repo)
    return d, run(repo, "approve", str(d), "--by", "OK")


def test_approve_refuses_an_aws_profile_whose_sso_session_ends_before_the_night(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 30)
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 1 and "dev" in r.stdout and "aws sso login" in r.stdout


def test_approve_takes_an_aws_profile_with_a_long_sso_session(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 24 * 60)
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 0, r.stdout + r.stderr


def test_approve_refuses_an_aws_profile_that_is_not_configured(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 24 * 60)
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "prod"}))
    assert r.returncode == 1 and "prod" in r.stdout


# --- レビューの承認の待ち ---

def review(*decisions):
    return [{"out": {"reviewDecision": x}} for x in decisions]


def review_await(repo, d, *extra):
    return night(repo, "await", str(d), "--kind", "review", "--pr", "7", "--interval", "0", *extra)


def test_await_review_waits_until_approved(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", review("REVIEW_REQUIRED", "REVIEW_REQUIRED", "APPROVED"))
    assert review_await(repo, d).returncode == 0


def test_await_review_wakes_main_on_requested_changes(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", review("CHANGES_REQUESTED"))
    assert review_await(repo, d).returncode == 1


def test_await_review_does_not_wait_when_no_review_is_required(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", review(""))
    r = review_await(repo, d)
    assert r.returncode == 1 and "要件ではない" in r.stdout


def test_a_review_wait_past_its_limit_parks_the_merge(repo, gh):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    gh.answers("pr view", review("REVIEW_REQUIRED"))
    assert review_await(repo, d, "--timeout-min", "0").returncode == 2
    assert run(repo, "check", str(d)).returncode == 0


# --- 通知 ---

@pytest.fixture
def osascript(tmp_path, monkeypatch):
    d = tmp_path / "fakeosa"
    d.mkdir()
    exe = d / "osascript"
    exe.write_text(f"#!/bin/sh\necho \"$@\" >> {d}/calls.log\n", encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    return d / "calls.log"


def test_lint_rejects_an_unknown_notification(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL, **{"通知": "メール"}), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "通知" in r.stdout


def test_done_and_block_notify_the_desktop(repo, osascript):
    d = full_spec(repo, "PR まで", **{"通知": "デスクトップ"})
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    assert osascript.exists() and "display notification" in osascript.read_text()
    calls = osascript.read_text().count("display notification")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    assert osascript.read_text().count("display notification") == calls + 1


def test_no_notification_without_the_row(repo, osascript):
    d = full_spec(repo, "PR まで")
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    assert not osascript.exists()


# --- 本番の状態の抜け道（壊れたまま・確かめていないを、出口が全部同じ判定で読む） ---

def test_a_passing_smoke_after_a_failed_one_does_not_leave_broken(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    assert smoke(repo, d, tmp_path, "pass", "again.txt").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout
    assert "本番: 壊れたまま" in night(repo, "report", str(d)).stdout.splitlines()[1]


def test_a_smoke_before_the_rollback_deploy_does_not_restore(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "early.txt").returncode == 0  # 戻したデプロイを待つ前
    assert "戻して確かめた" not in night(repo, "report", str(d)).stdout.splitlines()[1]


def test_a_deployed_production_without_a_smoke_is_not_done_even_with_the_qa_parked(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert night(repo, "park", str(d), "--kind", "qa", "--op", "実環境の QA", "--reason", "x").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout


def test_a_deploy_wait_that_times_out_leaves_production_unknown(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    sha = git_head(repo)
    gh.answers("pr view", [merged_pr(sha, sha)])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [{"out": []}])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0").returncode == 2
    assert "本番: 分からない" in night(repo, "report", str(d)).stdout.splitlines()[1]
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout


def test_the_stop_hook_keeps_blocking_past_twice_the_budget_while_production_is_unconfirmed(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    s = state(d)
    s["merged_at"] = time.time() - (s["post_budget_min"] * 3) * 60
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    out = json.loads(stop_hook(repo).stdout)
    assert out["decision"] == "block" and "ロールバック" in out["reason"]


def test_ready_rollback_refuses_a_revert_with_extra_changes(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    subprocess.run([*GIT, "revert", "--no-commit", sha], cwd=repo, check=True, capture_output=True)
    (repo / "extra.txt").write_text("x\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "revert and more"], cwd=repo, check=True)
    head = git_head(repo)
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head, "baseRefOid": sha}}])
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 1 and "戻して" in r.stdout


def test_ready_rollback_takes_a_revert_after_another_change_to_the_same_file(repo, gh, tmp_path):
    d = full_spec(repo)
    lib = repo / "lib.js"
    lib.write_text("".join(f"line {i}\n" for i in range(10)), encoding="utf-8")
    subprocess.run([*GIT, "add", "lib.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=repo, check=True)
    lib.write_text(lib.read_text(encoding="utf-8").replace("line 0", "line 0 by the spec"), encoding="utf-8")
    make_done(repo, d)  # spec のマージは lib.js の 1 行目を変える
    sha = merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "fail").returncode == 0
    lib.write_text(lib.read_text(encoding="utf-8").replace("line 9", "line 9 by another team"), encoding="utf-8")
    subprocess.run([*GIT, "commit", "-q", "-am", "another merge"], cwd=repo, check=True)
    rollback_pr(repo, gh, sha, base=git_head(repo))
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 0, r.stdout + r.stderr


def test_block_while_broken_needs_a_declared_reason_not_to_roll_back(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "x", "--evidence", "y")
    assert r.returncode != 0 and "ロールバック" in (r.stdout + r.stderr)
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "x", "--evidence", "y", "--no-rollback", "revert が衝突する")
    assert r.returncode == 0, r.stdout + r.stderr
    head = "\n".join(night(repo, "report", str(d)).stdout.splitlines()[:3])
    assert "戻していない: revert が衝突する" in head


def test_wait_is_refused_while_production_is_broken(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    r = run(repo, "wait", str(d), "--reason", "x")
    assert r.returncode != 0 and "ロールバック" in (r.stdout + r.stderr)


def test_a_rollback_by_command_restores_after_a_passing_smoke(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    broken(repo, gh, d, tmp_path)
    ev = tmp_path / "rb.txt"
    ev.write_text("$ ./rollback.sh\nok\n", encoding="utf-8")
    assert night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "smoke が落ちた").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "after.txt").returncode == 0
    assert "本番: 戻して確かめた" in night(repo, "report", str(d)).stdout.splitlines()[1]


def test_a_deployed_requirement_out_of_reworks_after_the_merge_demands_a_rollback(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "pass").returncode == 0
    s = state(d)
    s["reworks"] = {"R2": ["a", "b"]}
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    qa = (d / "qa.md").read_text(encoding="utf-8").replace("| R2 | pass |", "| R2 | fail |")
    (d / "qa.md").write_text(qa, encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout and "R2" in r.stdout


def test_lint_requires_the_aws_profile_row(repo):
    d = init_spec(repo)
    text = scoped(FULL).replace("- AWS の profile: なし\n", "")
    (d / "spec.md").write_text(text, encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "AWS の profile" in r.stdout


def test_lint_requires_the_deploy_check_for_deployed_requirements(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの確かめ": ""})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "デプロイの確かめ" in r.stdout


def test_approve_warns_but_takes_a_session_that_lasts_the_budget_but_not_twice(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 90)  # GOOD_SPEC の予算とマージ後の予算（30＋30 分）は越え、その 2 倍には届かない
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SSO" in r.stdout


def fake_aws(tmp_path, monkeypatch, code):
    fake = tmp_path / f"fakeaws{code}"
    fake.mkdir()
    (fake / "aws").write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8")
    (fake / "aws").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ['PATH']}")


def test_approve_does_not_refuse_a_refreshable_sso_session(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 30, refresh=True)
    fake_aws(tmp_path, monkeypatch, 0)  # 今のセッションで呼べる
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 0, r.stdout + r.stderr


def test_approve_refuses_a_refreshable_sso_session_that_no_longer_answers(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, -600, refresh=True)  # 昨日のセッションの cache だけが残っている
    fake_aws(tmp_path, monkeypatch, 255)
    _, r = approve_text(repo, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 1 and "SSO" in r.stdout


@pytest.mark.parametrize("marker", ["active: True", "  active: true", "active: true # 作業中", "active: yes"])
def test_approve_refuses_a_gdd_marker_that_gdd_reads_as_active_or_unreadable(repo, marker):
    gdd_on(repo)
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "gdd-dev.local.md").write_text(f"---\n{marker}\n---\n", encoding="utf-8")
    _, r = approve_text(repo, scoped(FULL))
    assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout


def test_approve_takes_an_inactive_gdd_marker(repo):
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "gdd-dev.local.md").write_text("---\nactive: false\n---\n", encoding="utf-8")
    _, r = approve_text(repo, scoped(FULL))
    assert "GDD" not in r.stdout


def test_lint_shows_the_overnight_prerequisites_before_the_spec_is_shown(repo):
    gdd_on(repo)
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "gdd-dev.local.md").write_text("---\nactive: true\n---\n", encoding="utf-8")
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout


def test_a_fix_after_a_confirmed_rollback_can_finish_the_night(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "restored.txt").returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "fix"], cwd=repo, check=True)  # 直しの PR
    fix = git_head(repo)
    gh.answers("pr view", [merged_pr(fix, fix)])
    assert night(repo, "merged", str(d), "--pr", "9").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "fixed.txt").returncode == 0
    r = run(repo, "wait", str(d), "--reason", "x")
    assert r.returncode == 0, r.stdout + r.stderr  # 戻して直して確かめた本番は、出口を止めない


def test_a_rollback_by_command_does_not_let_a_deployed_requirement_pass(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    broken(repo, gh, d, tmp_path)
    ev = tmp_path / "rb.txt"
    ev.write_text("$ ./rollback.sh\nok\n", encoding="utf-8")
    assert night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "smoke が落ちた").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "after.txt").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "R2" in r.stdout and "戻した後" in r.stdout


def test_a_slack_notification_carries_the_morning_report(repo):
    d = full_spec(repo, "PR まで", **{"通知": "Slack の DM"})
    r = night(repo, "notify", str(d))
    assert "人の判断を待つもの" in r.stdout


def test_approve_refuses_while_a_gdd_workflow_is_active(repo):
    gdd_on(repo)
    gdd_marker(repo)
    _, r = approve_text(repo, scoped(FULL))
    assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout


def test_approve_takes_an_active_gdd_marker_left_after_gdd_was_removed(repo):
    gdd_marker(repo)  # GDD の plugin はどの設定でも有効になっていない
    _, r = approve_text(repo, scoped(FULL))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gdd-dev.local.md" in r.stdout  # 残った lock は知らせる


def test_lint_passes_an_active_gdd_marker_whose_plugin_is_off_but_names_it(repo):
    gdd_on(repo, False)
    gdd_marker(repo)
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gdd-dev.local.md" in r.stdout


@pytest.mark.parametrize("user, project, local, refused", [
    (True, None, False, False),   # local が user を上書きする
    (False, True, None, True),    # project が user を上書きする
    (None, None, True, True),
    (True, False, None, False),
])
def test_approve_reads_the_gdd_plugin_with_the_later_scope_winning(repo, user, project, local, refused):
    for where, value in (("user", user), ("project", project), ("local", local)):
        if value is not None:
            gdd_on(repo, value, where)
    gdd_marker(repo)
    _, r = approve_text(repo, scoped(FULL))
    if refused:
        assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout, r.stdout + r.stderr
    else:
        assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("body", ["{broken", "[]", '{"enabledPlugins": []}'])
def test_approve_refuses_an_active_gdd_marker_when_a_settings_file_cannot_be_read(repo, body):
    f = repo.parent / ".claude-config" / "settings.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    gdd_marker(repo)
    _, r = approve_text(repo, scoped(FULL))
    assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout


def test_lint_warns_when_nothing_keeps_the_mac_awake(repo, tmp_path, monkeypatch):
    fake = tmp_path / "fakepmset"
    fake.mkdir()
    (fake / "pmset").write_text("#!/bin/sh\necho '   PreventUserIdleSystemSleep     0'\necho '   PreventSystemSleep 0'\n",
                                encoding="utf-8")
    (fake / "pmset").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ['PATH']}")
    _, r = approve_text(repo, with_budget(scoped(FULL), 90))
    assert "keep-awake" in r.stdout


def test_a_failed_desktop_notification_is_reported(repo, tmp_path, monkeypatch):
    fake = tmp_path / "badosa"
    fake.mkdir()
    (fake / "osascript").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (fake / "osascript").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ['PATH']}")
    d = full_spec(repo, "PR まで", **{"通知": "デスクトップ"})
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "通知を出せない" in r.stdout


def test_the_report_puts_a_rollback_among_what_waits_for_a_person(repo, gh, tmp_path):
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた").returncode == 0
    line = [x for x in night(repo, "report", str(d)).stdout.splitlines() if x.startswith("人の判断を待つもの")][0]
    assert "戻した" in line and "smoke が落ちた" in line


# --- コマンドでの戻しは、承認した宣言どおりのものだけを受ける ---

@pytest.mark.parametrize("value", ["./rollback.sh を打つ", "コマンド:", "コマンド:   "])
def test_lint_takes_only_the_revert_sentence_or_a_declared_command(repo, value):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL, **{"ロールバック": value}), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout


def test_lint_takes_a_declared_rollback_command(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL, **{"ロールバック": "コマンド: ./rollback.sh"}), encoding="utf-8")
    assert "ロールバック" not in run(repo, "lint", str(d)).stdout


def test_rolled_back_is_refused_on_a_revert_spec(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    ev = tmp_path / "rb.txt"
    ev.write_text("$ echo x\nx\n", encoding="utf-8")
    r = night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "smoke が落ちた")
    assert r.returncode != 0 and "revert" in (r.stdout + r.stderr)


def test_rolled_back_is_refused_for_a_command_other_than_the_declared_one(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    broken(repo, gh, d, tmp_path)
    ev = tmp_path / "rb.txt"
    ev.write_text("$ ./other.sh\nok\n", encoding="utf-8")
    r = night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "smoke が落ちた")
    assert r.returncode != 0 and "./rollback.sh" in (r.stdout + r.stderr)


def test_rolled_back_is_refused_for_evidence_written_before_production_broke(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    ev = tmp_path / "rb.txt"
    ev.write_text("$ ./rollback.sh\nok\n", encoding="utf-8")
    os.utime(ev, (1, 1))
    broken(repo, gh, d, tmp_path)
    r = night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "smoke が落ちた")
    assert r.returncode != 0


def test_a_broken_revert_spec_is_told_only_the_revert_path(repo, gh, tmp_path):
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    r = run(repo, "check", str(d))
    assert "rolled-back" not in r.stdout and "ready --rollback" in r.stdout


def test_a_broken_command_spec_is_told_the_declared_command(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    broken(repo, gh, d, tmp_path)
    r = run(repo, "check", str(d))
    assert "./rollback.sh" in r.stdout and "ready --rollback" not in r.stdout


def test_a_rollback_merge_on_a_command_deploy_spec_still_demands_a_check(repo, gh, tmp_path):
    d = full_spec(repo, **{"デプロイの起動": "コマンド: make deploy"})
    base_commit(repo)
    make_done(repo, d)
    sha = merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "pass").returncode == 0
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "梯子が尽きた").returncode == 0
    r = run(repo, "wait", str(d), "--reason", "x")
    assert r.returncode != 0 and "ロールバックの後" in (r.stdout + r.stderr)


def test_approve_reads_the_aws_profile_only_from_the_scope_section(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 30)
    text = scoped(FULL, **{"AWS の profile": "dev"})
    text = text.replace("## 自走の範囲", "<!--\n- AWS の profile: なし\n-->\n## 自走の範囲", 1)
    _, r = approve_text(repo, text)
    assert r.returncode == 1 and "dev" in r.stdout and "aws sso login" in r.stdout


def test_lint_refuses_a_scope_key_written_twice(repo):
    d = init_spec(repo)
    text = scoped(FULL, **{"AWS の profile": "dev"}).replace("- AWS の profile: dev", "- AWS の profile: なし\n- AWS の profile: dev")
    (d / "spec.md").write_text(text, encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "AWS の profile" in r.stdout and "2 本" in r.stdout


# --- 再設計: spec の値の読み手を 1 つにし、本番の状態を 1 つの導出で決める ---

def test_approve_fixes_the_budgets_from_the_constraints_without_comments(repo, gh, tmp_path):
    text = scoped(FULL).replace("- 予算: 30 分\n", "<!--\n- 予算: 600 分\n- マージ後の予算: 900 分\n-->\n- 予算: 30 分\n- マージ後の予算: 20 分\n")
    d, r = approve_text(repo, deployed(text))
    assert r.returncode == 0, r.stdout + r.stderr
    s = state(d)
    assert (s["budget_min"], s["post_budget_min"]) == (30, 20)
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert state(d)["post_budget_min"] == 20  # merged は spec を読み直さない


def test_lint_refuses_a_budget_written_only_inside_a_comment(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL).replace("- 予算: 30 分\n", "<!--\n- 予算: 30 分\n-->\n"), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "予算" in r.stdout


def test_approve_measures_the_sso_session_with_the_budget_it_records(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 100)  # 本文の予算（30＋30 分）なら足り、コメントの 600 分なら足りない
    text = scoped(FULL, **{"AWS の profile": "dev"}).replace("- 予算: 30 分\n", "<!--\n- 予算: 600 分\n-->\n- 予算: 30 分\n")
    d, r = approve_text(repo, text)
    assert r.returncode == 0 and state(d)["budget_min"] == 30, r.stdout


def test_a_fix_after_a_rollback_on_a_command_deploy_spec_is_still_rolled_back_when_it_cannot_pass(repo, gh, tmp_path):
    d = full_spec(repo, **{"デプロイの起動": "コマンド: make deploy"})
    sha = broken(repo, gh, d, tmp_path)
    head = rollback_pr(repo, gh, sha)
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "restored.txt").returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "fix"], cwd=repo, check=True)
    fix = git_head(repo)
    gh.answers("pr view", [merged_pr(fix, fix)])
    assert night(repo, "merged", str(d), "--pr", "9").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert smoke(repo, d, tmp_path, "pass", "fixed.txt").returncode == 0
    assert "戻して確かめた" not in night(repo, "report", str(d)).stdout.splitlines()[1]  # 載っているのは直し
    s = state(d)
    s["reworks"] = {"R2": ["a", "b"]}
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    qa = (d / "qa.md").read_text(encoding="utf-8").replace("| R2 | pass |", "| R2 | fail |")
    (d / "qa.md").write_text(qa, encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout and "R2" in r.stdout


def test_a_demanded_rollback_by_command_is_recorded_even_while_the_smoke_passes(repo, gh, tmp_path):
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    base_commit(repo)
    make_done(repo, d)
    merged_and_deployed(repo, gh, d)
    assert smoke(repo, d, tmp_path, "pass").returncode == 0
    s = state(d)
    s["reworks"] = {"R2": ["a", "b"]}
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    qa = (d / "qa.md").read_text(encoding="utf-8").replace("| R2 | pass |", "| R2 | fail |")
    (d / "qa.md").write_text(qa, encoding="utf-8")
    assert "./rollback.sh" in run(repo, "check", str(d)).stdout
    time.sleep(0.02)
    ev = tmp_path / "rb.txt"
    ev.write_text("$ ./rollback.sh\nok\n", encoding="utf-8")
    r = night(repo, "rolled-back", str(d), "--evidence", str(ev), "--reason", "作り直しが尽きた")
    assert r.returncode == 0, r.stdout + r.stderr
    assert smoke(repo, d, tmp_path, "pass", "after.txt").returncode == 0
    assert "本番: 戻して確かめた" in night(repo, "report", str(d)).stdout.splitlines()[1]


def with_budget(text, budget, post=None):
    """GOOD_SPEC 由来の spec の予算（30 分）を差し替える。post があればマージ後の予算も書く。"""
    return text.replace("- 予算: 30 分\n", f"- 予算: {budget} 分\n" + (f"- マージ後の予算: {post} 分\n" if post is not None else ""), 1)


def fake_mac(tmp_path, monkeypatch, batt="Now drawing from 'AC Power'", autoinstall="0", awake="1"):
    """pmset（assertions は既定で keep-awake が効いている形）と defaults を PATH に置く。"""
    fake = tmp_path / "fakemac"
    fake.mkdir()
    (fake / "pmset").write_text("#!/bin/sh\nif [ \"$2\" = batt ]; then echo \"" + batt + "\"; "
                                "else echo '   PreventUserIdleSystemSleep     " + awake + "'; fi\n", encoding="utf-8")
    (fake / "defaults").write_text(f"#!/bin/sh\necho {autoinstall}\n", encoding="utf-8")
    for f in fake.iterdir():
        f.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}{os.pathsep}{os.environ['PATH']}")


def test_approve_notes_a_mac_running_on_battery(repo, tmp_path, monkeypatch):
    fake_mac(tmp_path, monkeypatch, batt="Now drawing from 'Battery Power'")
    _, r = approve_text(repo, with_budget(scoped(FULL), 90))
    assert r.returncode == 0 and "電源につなぎ" in r.stdout and "蓋" in r.stdout


def test_approve_notes_automatic_macos_update_installs(repo, tmp_path, monkeypatch):
    fake_mac(tmp_path, monkeypatch, autoinstall="1")
    _, r = approve_text(repo, with_budget(scoped(FULL), 90))
    assert r.returncode == 0 and "自動インストール" in r.stdout


def test_approve_says_nothing_on_ac_power_without_automatic_installs(repo, tmp_path, monkeypatch):
    fake_mac(tmp_path, monkeypatch)
    _, r = approve_text(repo, scoped(FULL))
    assert r.returncode == 0 and "電源につなぎ" not in r.stdout and "自動インストール" not in r.stdout


NIGHT_NOTES = ("keep-awake", "電源につなぎ", "自動インストール", "見回り役")


def night_mac(tmp_path, monkeypatch):
    """4 つの夜の NOTE がすべて当たる Mac（keep-awake 無し・バッテリー・自動更新あり・見回り役の plist 無し）。"""
    fake_mac(tmp_path, monkeypatch, batt="Now drawing from 'Battery Power'", autoinstall="1", awake="0")
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))


def lint_or_approve(repo, how, text):
    if how == "approve":
        return approve_text(repo, text)[1]
    d = init_spec(repo)
    (d / "spec.md").write_text(text, encoding="utf-8")
    return run(repo, "lint", str(d))


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_30_minute_spec_gets_none_of_the_night_notes(repo, tmp_path, monkeypatch, how):
    night_mac(tmp_path, monkeypatch)
    r = lint_or_approve(repo, how, scoped(FULL))
    assert r.returncode == 0, r.stdout + r.stderr
    assert not [w for w in NIGHT_NOTES if w in r.stdout], r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
@pytest.mark.parametrize("budget, post", [(60, 0), (30, None), (20, 40)])
def test_a_spec_expected_to_end_within_an_hour_gets_none_of_the_night_notes(repo, tmp_path, monkeypatch, how, budget, post):
    night_mac(tmp_path, monkeypatch)
    r = lint_or_approve(repo, how, with_budget(scoped(FULL), budget, post))
    assert not [w for w in NIGHT_NOTES if w in r.stdout], r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
@pytest.mark.parametrize("budget, post", [(90, None), (30, 40), (61, 0), (60, 1)])
def test_a_spec_expected_to_run_over_an_hour_gets_every_night_note_that_applies(repo, tmp_path, monkeypatch, how, budget, post):
    night_mac(tmp_path, monkeypatch)
    r = lint_or_approve(repo, how, with_budget(scoped(FULL), budget, post))
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(w in r.stdout for w in NIGHT_NOTES), r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_spec_with_no_readable_budget_still_gets_the_night_notes(repo, tmp_path, monkeypatch, how):
    night_mac(tmp_path, monkeypatch)
    r = lint_or_approve(repo, how, scoped(FULL).replace("- 予算: 30 分\n", ""))
    assert all(w in r.stdout for w in NIGHT_NOTES), r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_30_minute_spec_still_stops_on_an_sso_session_that_ends_before_the_night(repo, tmp_path, monkeypatch, how):
    night_mac(tmp_path, monkeypatch)
    aws_home(tmp_path, monkeypatch, 30)
    r = lint_or_approve(repo, how, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 1 and "aws sso login" in r.stdout and "見込みの夜の終わり" in r.stdout
    assert not [w for w in NIGHT_NOTES if w in r.stdout], r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_30_minute_spec_still_notes_an_sso_session_that_ends_before_twice_the_budget(repo, tmp_path, monkeypatch, how):
    aws_home(tmp_path, monkeypatch, 100)  # 60 分の見込みには足り、2 倍（120 分）には足りない
    r = lint_or_approve(repo, how, scoped(FULL, **{"AWS の profile": "dev"}))
    assert r.returncode == 0 and "2 倍までは続かない" in r.stdout, r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_30_minute_spec_still_stops_on_an_active_gdd_marker(repo, tmp_path, monkeypatch, how):
    night_mac(tmp_path, monkeypatch)
    gdd_on(repo)
    gdd_marker(repo)
    r = lint_or_approve(repo, how, scoped(FULL))
    assert r.returncode == 1 and "GDD のワークフローが有効" in r.stdout
    assert not [w for w in NIGHT_NOTES if w in r.stdout], r.stdout


@pytest.mark.parametrize("how", ["lint", "approve"])
def test_a_30_minute_spec_still_notes_a_gdd_marker_left_after_gdd_was_removed(repo, tmp_path, monkeypatch, how):
    fake_mac(tmp_path, monkeypatch)
    gdd_marker(repo)
    r = lint_or_approve(repo, how, scoped(FULL))
    assert r.returncode == 0 and "gdd-dev.local.md" in r.stdout, r.stdout


# --- デプロイの起動がコマンドの spec では、マージだけでは本番の中身が変わらない ---

COMMAND_START = {"デプロイの起動": "コマンド: ./deploy.sh"}


def merged_only(repo, gh, d):
    sha = git_head(repo)
    gh.answers("pr view", [merged_pr(sha, sha)])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    return sha


def test_a_command_deploy_parked_after_the_merge_does_not_leave_production_unconfirmed(repo, gh, tmp_path):
    d = full_spec(repo, **COMMAND_START)
    base_commit(repo)
    make_done(repo, d)
    merged_only(repo, gh, d)
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "./deploy.sh", "--reason", "1 操作ごとの確認").returncode == 0
    assert "本番: この夜はデプロイしていない" in night(repo, "report", str(d)).stdout.splitlines()[1]
    r = run(repo, "check", str(d))
    assert "smoke" not in r.stdout and "ロールバック" not in r.stdout, r.stdout


def test_a_command_deploy_that_ran_leaves_production_to_be_confirmed_by_a_smoke(repo, gh, tmp_path):
    d = full_spec(repo, **COMMAND_START)
    base_commit(repo)
    make_done(repo, d)
    merged_only(repo, gh, d)
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert "本番: 分からない" in night(repo, "report", str(d)).stdout.splitlines()[1]
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "smoke" in r.stdout


def test_an_auto_deploy_merge_still_counts_as_a_change_to_production(repo, gh, tmp_path):
    d = full_spec(repo)
    base_commit(repo)
    make_done(repo, d)
    merged_only(repo, gh, d)
    assert "本番: 分からない" in night(repo, "report", str(d)).stdout.splitlines()[1]


def park_deploy(repo, d):
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "./deploy.sh", "--reason", "1 操作ごとの確認").returncode == 0


def test_an_annotated_auto_deploy_start_cannot_be_approved(repo):
    d = init_spec(repo)  # 許可値でもコマンドの形でもない起動は、park で数えなくなる形に入る前に承認で止める
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの起動": "マージで自動（deploy.yml）"})), encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 1 and "デプロイの起動" in r.stdout and state(d)["phase"] != "building"


def test_a_command_deploy_merge_without_a_park_still_counts(repo, gh, tmp_path):
    d = full_spec(repo, **COMMAND_START)
    base_commit(repo)
    make_done(repo, d)
    merged_only(repo, gh, d)  # 打ったかもしれないが、待ちの記録も park も無い
    assert "本番: 分からない" in night(repo, "report", str(d)).stdout.splitlines()[1]


def test_an_unreadable_await_row_still_lets_the_rollback_run_to_the_end(repo, gh, tmp_path):
    """待ちの記録に読めない行があっても、壊れた本番の戻し（ready --rollback・merged --rollback・deploy の待ち・smoke）は回り、
    最後は block --no-rollback で人に渡せ、朝の報告も出る。smoke は、読めない行がある間は記録のファイルの更新より後のものだけを受ける。"""
    d = full_spec(repo)
    sha = broken(repo, gh, d, tmp_path)
    with (d / "awaits.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"kind": "deploy", "sha": "x", "res\n')
    assert "awaits.jsonl:" in run(repo, "check", str(d)).stderr
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "x", "--evidence", "y")
    assert r.returncode != 0 and "awaits.jsonl:" in r.stdout + r.stderr and "ロールバック" in r.stdout + r.stderr  # 先に戻すよう促す
    head = rollback_pr(repo, gh, sha)
    r = night(repo, "ready", str(d), "--pr", "8", "--rollback")
    assert r.returncode == 0, r.stdout + r.stderr
    gh.answers("pr view", [merged_pr(head, head)])
    assert night(repo, "merged", str(d), "--pr", "8", "--rollback", "--reason", "smoke が落ちた").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    early = tmp_path / "early.txt"
    early.write_text("smoke pass\n", encoding="utf-8")
    os.utime(early, (time.time() - 3600, time.time() - 3600))
    assert night(repo, "qa", str(d), "--evidence", str(early), "--smoke", "pass").returncode != 0
    assert smoke(repo, d, tmp_path, "pass", "smoke2.txt").returncode == 0
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "戻した", "--evidence", "smoke2.txt",
            "--no-rollback", "戻したが、待ちの記録が読めず確かめを数えられない")
    assert r.returncode == 0, r.stdout + r.stderr
    out = night(repo, "report", str(d))
    assert out.returncode == 0 and "awaits.jsonl:" in out.stdout and "block: R2" in out.stdout


def cut_await_row(d):
    time.sleep(0.02)
    with (d / "awaits.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"kind": "deploy", "sha": "x", "res\n')


def written(tmp_path, name, text):
    ev = tmp_path / name
    ev.write_text(text, encoding="utf-8")
    time.sleep(0.02)
    return ev


def test_with_an_unreadable_await_row_qa_takes_only_evidence_newer_than_the_record_file(repo, gh, tmp_path):
    """読めない行があるときの smoke は、読める deploy の後でも、記録のファイルの更新より前なら受けない（消えた deploy の後とは言えない）。"""
    d = full_spec(repo)
    broken(repo, gh, d, tmp_path)
    old = written(tmp_path, "old.txt", "smoke pass\n")
    cut_await_row(d)
    assert night(repo, "qa", str(d), "--evidence", str(old), "--smoke", "pass").returncode != 0
    new = written(tmp_path, "new.txt", "smoke pass\n")
    assert night(repo, "qa", str(d), "--evidence", str(new), "--smoke", "pass").returncode == 0


def test_with_an_unreadable_await_row_a_rollback_by_command_still_runs(repo, gh, tmp_path):
    """コマンドで戻す spec でも、読めない行があるまま rolled-back が回り（記録のファイルの更新より後の出力だけ）、block で人に渡せる。"""
    d = full_spec(repo, **{"ロールバック": "コマンド: ./rollback.sh"})
    broken(repo, gh, d, tmp_path)
    old = written(tmp_path, "rb-old.txt", "$ ./rollback.sh\nok\n")
    cut_await_row(d)
    assert night(repo, "rolled-back", str(d), "--evidence", str(old), "--reason", "smoke が落ちた").returncode != 0
    new = written(tmp_path, "rb.txt", "$ ./rollback.sh\nok\n")
    r = night(repo, "rolled-back", str(d), "--evidence", str(new), "--reason", "smoke が落ちた")
    assert r.returncode == 0, r.stdout + r.stderr
    assert smoke(repo, d, tmp_path, "pass", "after.txt").returncode == 0
    r = run(repo, "block", str(d), "--req", "R2", "--reason", "戻した", "--evidence", "after.txt", "--no-rollback", "記録が読めない")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_report_does_not_say_done_while_an_await_row_is_unreadable(repo, gh, tmp_path):
    """読めない行があるときの朝の報告は、pass の要件も done と書かない（消えた待ちの記録に積んだ段が入っていたかもしれない）。
    Slack の DM の知らせにも、その報告の行を載せる。"""
    d = full_spec(repo, **{"通知": "Slack の DM"})
    broken(repo, gh, d, tmp_path)
    cut_await_row(d)
    assert run(repo, "block", str(d), "--req", "R2", "--reason", "x", "--evidence", "y", "--no-rollback", "z").returncode == 0
    out = night(repo, "report", str(d)).stdout
    reqs = [x for x in out.splitlines() if x.startswith("- R")]
    assert reqs and not any(": done" in x for x in reqs) and any("待ちの記録が読めない" in x for x in reqs)
    note = night(repo, "notify", str(d)).stdout
    assert "block: R2" in note and "awaits.jsonl:" in note
