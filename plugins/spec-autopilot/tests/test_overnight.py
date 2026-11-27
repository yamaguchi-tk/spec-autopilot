"""scripts/overnight.py（PR の後のループ: 機械の待ち・マージの記録・park・実装役の報告の確かめ・朝の報告）と、
それを読む lint・check・Stop hook を、入口（CLI と hook）から通して確かめる。gh は PATH に置いた偽物で答える。"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_autopilot import (GOOD_SPEC, PLUGIN, approved, hand_off, implementer_ran, init_spec, make_done, repo, run, state,  # noqa: F401
                            stop_hook, user_says)

OVERNIGHT = PLUGIN / "scripts" / "overnight.py"
sys.path.insert(0, str(PLUGIN / "scripts"))
FULL = "マージ・デプロイ・QA まで"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(" ".join(args) + "\n")
key = " ".join(args[:2])
path = os.path.join(d, "script.json")
script = json.load(open(path))
seq = script.get(key)
if seq is None:
    sys.stderr.write("fake gh: no answer for " + key + "\n")
    sys.exit(1)
ans = seq[0] if len(seq) == 1 else seq.pop(0)
json.dump(script, open(path, "w"))
out = ans.get("out", "")
sys.stdout.write(out if isinstance(out, str) else json.dumps(out))
sys.exit(ans.get("code", 0))
'''


def scoped(scope=FULL, **rows):
    """GOOD_SPEC の自走の範囲を差し替える。"""
    vals = {"範囲": scope, "QA の環境": "本番の test チャネル", "QA の書き込み先": "#bot-test への投稿",
            "デプロイの起動": "マージで自動", "デプロイの確かめ": "deploy",
            "ロールバック": "revert の PR をマージし、デプロイの完了を確かめる", "AWS の profile": "なし", **rows}
    body = "\n".join(f"- {k}: {v}".rstrip() for k, v in vals.items())
    start = GOOD_SPEC.index("## 自走の範囲")
    end = GOOD_SPEC.index("## ", start + 3)
    return GOOD_SPEC[:start] + "## 自走の範囲\n" + body + "\n\n" + GOOD_SPEC[end:]


R2_LOCAL = "| R2 | 手元で実物 | ブラウザで操作 | 再開後に盤面が空になる |"


def deployed(text):
    """R2 の段をデプロイ後にする（マージ後の QA のループを通る spec）。"""
    return text.replace(R2_LOCAL, R2_LOCAL.replace("手元で実物", "デプロイ後")
                        + "\n\n- 手元でできない理由: R2（bot をローカルで起動できない）")


@pytest.fixture
def gh(tmp_path, monkeypatch):
    """偽の gh を PATH の先頭に置く。answers(key, [答え...]) で答えを並べ、calls() で呼ばれた引数を読む。"""
    d = tmp_path / "fakegh"
    d.mkdir()
    exe = d / "gh"
    exe.write_text(FAKE_GH, encoding="utf-8")
    exe.chmod(0o755)
    (d / "script.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_DIR", str(d))

    class G:
        def answers(self, key, seq):
            s = json.loads((d / "script.json").read_text())
            s[key] = seq
            (d / "script.json").write_text(json.dumps(s))

        def calls(self):
            f = d / "calls.log"
            return f.read_text().splitlines() if f.exists() else []
    return G()


def night(repo, *args):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s1"}
    return subprocess.run([sys.executable, str(OVERNIGHT), *args], cwd=repo, capture_output=True, text=True, env=env,
                          timeout=60)


def full_spec(repo, scope=FULL, **rows):
    d = init_spec(repo)
    text = scoped(scope, **rows)
    (d / "spec.md").write_text(deployed(text) if scope == FULL else text, encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def checks(*buckets):
    return {"out": [{"name": f"job{i}", "bucket": b, "link": f"https://github.com/o/r/actions/runs/{100 + i}/job/{9 + i}"}
                    for i, b in enumerate(buckets)]}


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def git_head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def merged_pr(head, sha="m1"):
    return {"out": {"state": "MERGED", "mergedAt": "2026-11-22T00:00:00Z", "mergeCommit": {"oid": sha}, "headRefOid": head}}


def awaits(d):
    f = d / "awaits.jsonl"
    return [json.loads(x) for x in f.read_bytes().decode("utf-8").split("\n") if x] if f.exists() else []


def deploy_ok():
    return {"out": [{"databaseId": 5, "workflowName": "deploy", "status": "completed", "conclusion": "success"}]}


# --- lint の自走の範囲 ---

def test_lint_requires_the_scope_section(repo):
    d = init_spec(repo)
    text = GOOD_SPEC.replace(GOOD_SPEC[GOOD_SPEC.index("## 自走の範囲"):GOOD_SPEC.index("## 止まる条件")], "")
    (d / "spec.md").write_text(text, encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "自走の範囲" in r.stdout


@pytest.mark.parametrize("scope", ["マージ・デプロイ・QA まで", "マージまで", "PR まで"])
def test_lint_accepts_the_three_scopes(repo, scope):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(scope), encoding="utf-8")
    assert run(repo, "lint", str(d)).returncode == 0


@pytest.mark.parametrize("scope", ["", "全部", "マージ・デプロイまで"])
def test_lint_rejects_an_unknown_scope(repo, scope):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(scope), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "範囲" in r.stdout


@pytest.mark.parametrize("row", ["QA の環境", "QA の書き込み先", "デプロイの起動", "ロールバック"])  # 依頼の 4 行
def test_lint_requires_the_rows_for_deploy_and_qa(repo, row):
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{row: ""})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and row in r.stdout


def workflows(repo, files):
    """repo の .github/workflows に {ファイル名: 本文} を書く。"""
    w = repo / ".github" / "workflows"
    w.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (w / name).write_text(body, encoding="utf-8")


LAMBDA_DEPLOY = {"lambda-deploy.yaml": "name: lambda deploy\non:\n  push:\n    branches: [main]\njobs: {}\n"}


def test_lint_accepts_a_deploy_check_that_names_the_workflow(repo):
    # await --kind deploy は gh の workflowName と照らすので、`name:` の値なら通る
    workflows(repo, LAMBDA_DEPLOY)
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの確かめ": "lambda deploy"})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout


def test_lint_rejects_a_deploy_check_that_names_the_workflow_file(repo):
    # 2026-11-26 の事例: ファイル名を書くと await が照合できず、承認の後は直せない
    workflows(repo, LAMBDA_DEPLOY)
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの確かめ": "lambda-deploy"})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "lambda-deploy" in r.stdout and "`lambda deploy`" in r.stdout


def test_lint_rejects_a_deploy_check_that_names_no_workflow(repo):
    workflows(repo, LAMBDA_DEPLOY)
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの確かめ": "lambda deploy、nope"})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "nope" in r.stdout


def test_lint_reads_an_unnamed_workflow_by_its_path(repo):
    # `name:` の無い workflow は、GitHub が workflow のパスを workflowName にする
    workflows(repo, {"deploy.yml": "on: push\njobs: {}\n"})
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの確かめ": ".github/workflows/deploy.yml"})),
                               encoding="utf-8")
    assert run(repo, "lint", str(d)).returncode == 0


def test_lint_lets_the_merge_scope_leave_the_deploy_rows_empty(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped("マージまで", **{"QA の環境": "", "デプロイの起動": "", "ロールバック": ""}),
                               encoding="utf-8")
    assert run(repo, "lint", str(d)).returncode == 0


def test_lint_notes_a_deploy_that_is_not_started_by_the_merge(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの起動": "コマンド: make deploy"})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 0 and "NOTE" in r.stdout and "デプロイの起動" in r.stdout


@pytest.mark.parametrize("start", ["make deploy", "マージで自動（deploy.yml）", "コマンド:"])
def test_lint_rejects_a_deploy_start_that_is_neither_the_merge_nor_a_command_row(repo, start):
    d = init_spec(repo)
    (d / "spec.md").write_text(deployed(scoped(FULL, **{"デプロイの起動": start})), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "`- デプロイの起動:` は「マージで自動」か「コマンド: <1 行のコマンド>」" in r.stdout


def test_lint_rejects_a_missing_row(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(scoped(FULL).replace("- ロールバック: revert の PR をマージし、デプロイの完了を確かめる\n", ""),
                               encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1 and "ロールバック" in r.stdout


# --- check の範囲（done は QA の後） ---

def test_check_keeps_the_pr_scope_as_before(repo):
    d = full_spec(repo, "PR まで")
    make_done(repo, d)
    assert run(repo, "check", str(d)).returncode == 0


def test_check_reads_a_spec_without_the_section_as_the_pr_scope(repo):
    d = full_spec(repo, "PR まで")
    make_done(repo, d)
    text = (d / "spec.md").read_text(encoding="utf-8")
    s = state(d)
    (d / "spec.md").write_text(text[:text.index("## 自走の範囲")] + text[text.index("## 止まる条件"):], encoding="utf-8")
    import autopilot  # noqa: E402
    s["spec_sha256"] = autopilot.sha(d)  # 節の無い旧い版で承認した spec
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert run(repo, "check", str(d)).returncode == 0


def test_check_requires_a_merge_that_contains_head(repo, gh):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "overnight.py merged" in r.stdout
    assert run(repo, "check", str(d), "--stage", "pr").returncode == 0  # PR を作る前の検査はマージを見ない
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    assert run(repo, "check", str(d)).returncode == 0
    (repo / "fix.js").write_text("y\n", encoding="utf-8")  # マージの後の直し（まだマージしていない）
    hand_off(repo, d)
    assert run(repo, "review", str(d), "--high", "none").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "マージ" in r.stdout


def test_check_requires_the_deploy_of_the_merge_and_a_qa_after_it(repo, gh, tmp_path):
    d = full_spec(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイ" in r.stdout
    gh.answers("run list", [deploy_ok()])
    r = night(repo, "await", str(d), "--kind", "deploy", "--interval", "0")
    assert r.returncode == 0, r.stdout + r.stderr
    assert awaits(d)[-1]["sha"] == "m1"
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "overnight.py qa" in r.stdout
    time.sleep(0.02)
    ev = tmp_path / "qa-evidence.txt"
    ev.write_text("posted to #bot-test and saw the reply\n", encoding="utf-8")
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "pass").returncode == 0
    (d / "evidence" / "R2.txt").write_text("- commit: m1\n- 結果: Confirmed\n$ post #bot-test\nR2 checked in #bot-test after the deploy\n",
                                           encoding="utf-8")
    assert run(repo, "check", str(d)).returncode == 0


def test_qa_refuses_evidence_from_before_the_deploy(repo, gh, tmp_path):
    d = full_spec(repo)
    make_done(repo, d)
    ev = tmp_path / "old.txt"
    ev.write_text("old\n", encoding="utf-8")
    time.sleep(0.02)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "pass").returncode != 0


def test_check_accepts_a_parked_merge_instead(repo):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    r = night(repo, "park", str(d), "--kind", "merge", "--op", "gh pr merge 7", "--reason", "branch protection に断られた")
    assert r.returncode == 0, r.stderr
    assert run(repo, "check", str(d)).returncode == 0


def test_park_rejects_an_unknown_kind(repo):
    d = full_spec(repo, "マージまで")
    assert night(repo, "park", str(d), "--kind", "all", "--op", "x", "--reason", "y").returncode != 0


# --- await ---

def ci_await(repo, d, *extra):
    return night(repo, "await", str(d), "--kind", "ci", "--pr", "7", "--interval", "0", *extra)


def test_await_ci_exits_zero_when_every_check_passes(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("pending", "pass"), checks("pass", "skipping")])
    r = ci_await(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["phase"] == "building" and not (d / "await.json").exists()
    assert awaits(d)[-1]["result"] == "success" and awaits(d)[-1]["sha"] == "h7"


def test_await_starts_a_new_line_after_a_cut_record(repo, gh):
    """前の記録が途中で切れていても、次の記録を同じ行につなげず、新しい行に書く。"""
    d = full_spec(repo)
    (d / "awaits.jsonl").write_text('{"kind": "deploy", "sha": "m0", "res', encoding="utf-8")
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("pass")])
    ci_await(repo, d)
    lines = (d / "awaits.jsonl").read_bytes().decode("utf-8").split("\n")
    assert lines[0] == '{"kind": "deploy", "sha": "m0", "res' and json.loads(lines[1])["sha"] == "h7"


def test_await_does_not_take_no_runs_or_only_skips_as_success(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [{"out": []}, checks("skipping")])
    assert ci_await(repo, d, "--timeout-min", "0.001").returncode == 2


def test_await_exits_at_the_first_failure_without_waiting_for_the_rest(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("fail", "pending")])
    gh.answers("run view", [{"out": {"attempt": 1}}, {"out": "AssertionError: boom"}])
    r = ci_await(repo, d)
    assert r.returncode == 1 and "job0" in r.stdout


def test_await_hands_a_first_attempt_flake_back_to_main(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("fail")])
    gh.answers("run view", [{"out": {"attempt": 1}}, {"out": "Error: Error acquiring the state lock"}])
    r = ci_await(repo, d)
    assert r.returncode == 3 and "gh run rerun 100 --failed" in r.stdout
    assert not [c for c in gh.calls() if c.startswith("run rerun")]  # 再実行は main が自分の Bash で打つ


def test_await_does_not_rerun_a_flake_twice(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("fail")])
    gh.answers("run view", [{"out": {"attempt": 2}}, {"out": "Error: Error acquiring the state lock"}])
    assert ci_await(repo, d).returncode == 1


def test_await_parks_when_the_limit_passes(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("pending")])
    assert ci_await(repo, d, "--timeout-min", "0").returncode == 2
    r = night(repo, "report", str(d))
    assert "ci の待ち" in r.stdout


def test_await_treats_an_unknown_bucket_as_a_failure(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("weird")])
    gh.answers("run view", [{"out": {"attempt": 1}}, {"out": ""}])
    assert ci_await(repo, d).returncode == 1


def test_await_waits_for_every_named_workflow(repo, gh):
    d = full_spec(repo, **{"デプロイの確かめ": "deploy、apply"})
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    r = night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0.001")
    assert r.returncode == 2  # apply がまだ起きていない


def test_the_wait_is_not_counted_in_the_budget(repo, gh):
    import autopilot  # noqa: E402
    import overnight  # noqa: E402
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("pending"), checks("pending"), checks("pass")])
    before = overnight.budget_view(d, autopilot.load_state(d))[0]
    assert ci_await(repo, d, "--interval", "0.5").returncode == 0
    assert overnight.budget_view(d, autopilot.load_state(d))[0] < before + 0.5 / 60


def test_await_refuses_a_relative_dir_and_a_spec_that_is_not_building(repo, gh):
    d = full_spec(repo)
    assert night(repo, "await", os.path.relpath(d, repo), "--kind", "ci", "--pr", "7").returncode != 0
    d2 = init_spec(repo, "other")
    assert night(repo, "await", str(d2), "--kind", "ci", "--pr", "7").returncode != 0


# --- Stop hook と await（fail-open の側を先に） ---

def start_await(repo, d, gh):
    gh.answers("pr view", [{"out": {"headRefOid": "h7"}}])
    gh.answers("pr checks", [checks("pending")])
    p = subprocess.Popen([sys.executable, str(OVERNIGHT), "await", str(d), "--kind", "ci", "--pr", "7", "--interval", "0.2"],
                         cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if (d / "await.json").exists():
            return p
        time.sleep(0.05)
    p.kill()
    raise AssertionError("await が await.json を書かなかった")


NARROW_PS = """#!/bin/sh
# 端末でない出力の command の列を切る ps（Linux の procps の形）。-ww を渡したときだけ切らない
for a in "$@"; do [ "$a" = "-ww" ] && exec /bin/ps "$@"; done
/bin/ps "$@" | cut -c1-60
"""


@pytest.fixture
def narrow_ps(tmp_path, monkeypatch):
    d = tmp_path / "narrowps"
    d.mkdir()
    (d / "ps").write_text(NARROW_PS, encoding="utf-8")
    (d / "ps").chmod(0o755)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")


def test_stop_hook_releases_the_await_when_ps_cuts_the_command(repo, gh, narrow_ps):
    d = full_spec(repo)
    p = start_await(repo, d, gh)
    try:
        time.sleep(1.1)
        r = stop_hook(repo)
        assert '"block"' not in r.stdout, r.stdout
    finally:
        p.kill()
        p.wait()


def test_watch_sees_the_await_when_ps_cuts_the_command(repo, gh, narrow_ps):
    d = full_spec(repo)
    p = start_await(repo, d, gh)
    try:
        code = ("import sys, overnight, watch; print(watch.awaiting(overnight, __import__('pathlib').Path(sys.argv[1])))")
        r = subprocess.run([sys.executable, "-c", code, str(d)], capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": f"{PLUGIN / 'scripts'}{os.pathsep}{PLUGIN / 'hooks'}"})
        assert r.stdout.strip() == "True", r.stdout + r.stderr
    finally:
        p.kill()
        p.wait()


def test_stop_hook_releases_while_the_await_process_lives(repo, gh):
    d = full_spec(repo)
    p = start_await(repo, d, gh)
    try:
        time.sleep(1.1)
        r = stop_hook(repo)
        assert '"block"' not in r.stdout, r.stdout
    finally:
        p.kill()
        p.wait()


def test_stop_hook_blocks_when_the_await_process_died(repo, gh):
    d = full_spec(repo)
    p = start_await(repo, d, gh)
    p.kill()
    p.wait()
    assert (d / "await.json").exists()  # SIGKILL では後始末が走らない
    r = stop_hook(repo, {"stop_hook_active": True})
    assert '"block"' in r.stdout  # 続行中でも止める（読めない spec の弁に回さない）


def test_stop_hook_blocks_when_the_await_deadline_passed(repo, gh):
    d = full_spec(repo)
    p = start_await(repo, d, gh)
    try:
        rec = json.loads((d / "await.json").read_text())
        rec["deadline"] = time.time() - 1  # gh が返らずに固まった待ちを、ずっと放さない
        (d / "await.json").write_text(json.dumps(rec))
        assert '"block"' in stop_hook(repo).stdout
    finally:
        p.kill()
        p.wait()


@pytest.mark.parametrize("record", ['{"pid": "x"}', '{"pid": true, "started_at": 1, "deadline": 9e12}', '"broken"', "{",
                                    '{"pid": -1, "started_at": 1, "deadline": 9e12}'])
def test_stop_hook_blocks_when_the_await_record_is_unreadable(repo, record):
    d = full_spec(repo)
    (d / "await.json").write_text(record, encoding="utf-8")
    assert '"block"' in stop_hook(repo).stdout


def test_stop_hook_blocks_when_the_pid_is_some_other_process(repo):
    d = full_spec(repo)
    (d / "await.json").write_text(json.dumps({"pid": os.getpid(), "started_at": time.time(), "deadline": time.time() + 600}))
    assert '"block"' in stop_hook(repo).stdout  # 生きているが、spec の await ではない


def test_stop_hook_blocks_an_await_of_another_spec(repo, gh):
    d = full_spec(repo)
    other = init_spec(repo, "other")
    p = start_await(repo, d, gh)
    try:
        (other / "await.json").write_text((d / "await.json").read_text())
        (d / "await.json").unlink()
        assert '"block"' in stop_hook(repo).stdout
    finally:
        p.kill()
        p.wait()


# --- マージ・予算・関門 ---

def test_merged_refuses_an_unmerged_pr(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [{"out": {"state": "OPEN", "mergedAt": None, "mergeCommit": None, "headRefOid": "h1"}}])
    r = night(repo, "merged", str(d), "--pr", "7")
    assert r.returncode == 1 and not state(d).get("merges")


def test_merged_is_idempotent(repo, gh):
    d = full_spec(repo)
    gh.answers("pr view", [merged_pr("h1")])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    at = state(d)["merged_at"]
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    s = state(d)
    assert len(s["merges"]) == 1 and s["merged_at"] == at


def test_the_post_merge_budget_is_counted_from_the_merge(repo, gh):
    d = full_spec(repo)
    s = state(d)
    s["approved_at"] = time.time() - 10_000 * 60  # 承認からは予算の 2 倍をとうに過ぎた
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    assert '"block"' not in stop_hook(repo).stdout
    gh.answers("pr view", [merged_pr("h1")])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    out = json.loads(stop_hook(repo).stdout)
    assert out["decision"] == "block" and "マージ後" in out["reason"]  # マージ後の予算の中なので止める


def wait_for_deploy(d):
    """デプロイ後の R2 を、PR の前の値（unverified（デプロイ後に確かめる））にする。"""
    qa = (d / "qa.md").read_text(encoding="utf-8").replace(
        "| R2 | pass | cmd: playwright でEnterを押し盤面が空になった |", "| R2 | unverified | デプロイ後に確かめる |")
    (d / "qa.md").write_text(qa, encoding="utf-8")


def test_ready_requires_the_reviewed_head_and_ci_on_it(repo, gh):
    d = full_spec(repo)
    make_done(repo, d)
    wait_for_deploy(d)
    head = git_head(repo)
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": head}}])
    r = night(repo, "ready", str(d), "--pr", "7")
    assert r.returncode == 1 and "CI" in r.stdout
    gh.answers("pr checks", [checks("pass")])
    assert ci_await(repo, d).returncode == 0
    assert night(repo, "ready", str(d), "--pr", "7").returncode == 0
    gh.answers("pr view", [{"out": {"state": "OPEN", "headRefOid": "0" * 40}}])
    r = night(repo, "ready", str(d), "--pr", "7")
    assert r.returncode == 1 and "評価役" in r.stdout


# --- 実装役の報告の確かめ ---

def test_review_requires_a_handoff_at_head(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    r = run(repo, "review", str(d), "--high", "none")
    assert r.returncode != 0 and "handoff" in r.stderr
    hand_off(repo, d)
    assert run(repo, "review", str(d), "--high", "none").returncode == 0


def test_handoff_requires_a_new_commit_and_checked_tasks(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")  # dispatch は tasks.md にあるタスクだけを受ける
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    implementer_ran()
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "commit" in r.stdout and "T1" in r.stdout
    (repo / "core.js").write_text("x\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "core.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "impl"], cwd=repo, check=True)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0


def test_handoff_rejects_uncommitted_code(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    (repo / "core.js").write_text("x\n", encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "core.js" in r.stdout


def test_check_requires_a_review_of_the_current_code(repo):
    d = full_spec(repo, "PR まで")
    make_done(repo, d)
    (repo / "core.js").write_text("changed\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "core.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "after review"], cwd=repo, check=True)
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "レビュー" in r.stdout


# --- 朝の報告 ---

def test_done_prints_the_morning_report_with_what_waits_for_a_human(repo):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    assert night(repo, "park", str(d), "--kind", "merge", "--op", "gh pr merge 7", "--reason", "必須レビュー").returncode == 0
    r = run(repo, "done", str(d))
    assert r.returncode == 0, r.stdout
    head = r.stdout[r.stdout.index("朝の報告"):]
    assert "人の判断を待つ" in head and "gh pr merge 7" in head
    assert "R1: done" not in head and "R2: done" not in head  # マージを積んだので、マージに頼る要件を done と書かない
    assert "R1: 確かめていない" in head


def test_the_morning_report_says_when_nothing_waits(repo):
    d = full_spec(repo, "PR まで")
    make_done(repo, d)
    r = night(repo, "report", str(d))
    assert r.returncode == 0 and "人の判断を待つものは無い" in r.stdout


# --- 独立レビュー 1 巡目の指摘（承認し直し・park の範囲・rebase・冪等・朝の報告） ---

def block_and_reapprove(repo, d, *extra):
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y", *extra).returncode == 0
    time.sleep(0.02)
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr


def test_reapproving_after_a_post_merge_block_starts_a_fresh_round(repo, gh):
    d = full_spec(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    s = state(d)
    s["merged_at"] = time.time() - 10_000 * 60  # マージ後の予算の 2 倍をとうに過ぎて block した
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    block_and_reapprove(repo, d, "--no-rollback", "本番を確かめないまま予算を過ぎた")  # 確かめていない本番は理由が要る
    s = state(d)
    assert not s.get("merges") and s.get("merged_at") is None and s["history"][-1].get("merges")
    out = json.loads(stop_hook(repo).stdout)
    assert out["decision"] == "block"  # 新しい巡は承認から数え直すので、止める


def test_a_park_from_before_the_reapproval_does_not_exempt_the_new_round(repo):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    assert night(repo, "park", str(d), "--kind", "merge", "--op", "gh pr merge 7", "--reason", "必須レビュー").returncode == 0
    block_and_reapprove(repo, d)
    make_done(repo, d)
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "マージ" in r.stdout


def test_a_qa_park_for_one_requirement_does_not_exempt_the_qa_of_the_others(repo, gh, tmp_path):
    d = full_spec(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    r = night(repo, "park", str(d), "--kind", "qa", "--op", "本番 DB への書き込み", "--reason", "範囲の外", "--req", "R2")
    assert r.returncode == 0, r.stderr
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "overnight.py qa" in r.stdout


def test_a_deploy_timeout_of_an_earlier_merge_does_not_exempt_the_next_merge(repo, gh):
    d = full_spec(repo)
    make_done(repo, d)
    gh.answers("pr view", [merged_pr(git_head(repo), "m1")])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [{"out": [{"databaseId": 5, "workflowName": "deploy", "status": "in_progress", "conclusion": None}]}])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0", "--timeout-min", "0").returncode == 2
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    hand_off(repo, d)
    assert run(repo, "review", str(d), "--high", "none").returncode == 0
    gh.answers("pr view", [merged_pr(git_head(repo), "m2")])
    assert night(repo, "merged", str(d), "--pr", "8").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイ" in r.stdout


def test_a_park_before_the_last_merge_does_not_exempt_the_stages_after_it(repo, gh):
    d = full_spec(repo)
    make_done(repo, d)
    assert night(repo, "park", str(d), "--kind", "deploy", "--op", "deploy", "--reason", "範囲の外").returncode == 0
    gh.answers("pr view", [merged_pr(git_head(repo), "m1")])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "デプロイ" in r.stdout


def test_handoff_passes_after_a_rebase(repo):
    d = full_spec(repo)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)  # 枝を分ける元の commit
    base = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    subprocess.run([*GIT, "checkout", "-q", "-b", "work"], cwd=repo, check=True)
    make_done(repo, d)
    subprocess.run([*GIT, "checkout", "-q", base], cwd=repo, check=True)
    (repo / "other.txt").write_text("main moved\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "other.txt"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "main moved"], cwd=repo, check=True)
    subprocess.run([*GIT, "checkout", "-q", "work"], cwd=repo, check=True)
    subprocess.run([*GIT, "rebase", "-q", base], cwd=repo, check=True, capture_output=True)
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert run(repo, "review", str(d), "--high", "none").returncode == 0


def test_handoff_requires_a_dispatch_and_a_task(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "dispatch" in r.stdout
    assert night(repo, "handoff", str(d)).returncode != 0  # --task は省けない


def test_handoff_park_and_qa_are_idempotent(repo, gh, tmp_path):
    d = full_spec(repo)
    make_done(repo, d)
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0  # 同じ HEAD でもう一度
    assert len(state(d)["handoffs"]) == 1
    for _ in range(2):
        assert night(repo, "park", str(d), "--kind", "other", "--op", "x", "--reason", "y").returncode == 0
    assert len(state(d)["parked"]) == 1
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    gh.answers("run list", [deploy_ok()])
    assert night(repo, "await", str(d), "--kind", "deploy", "--interval", "0").returncode == 0
    time.sleep(0.02)
    ev = tmp_path / "qa.txt"
    ev.write_text("ok\n", encoding="utf-8")
    for _ in range(2):
        assert night(repo, "qa", str(d), "--evidence", str(ev), "--smoke", "pass").returncode == 0
    assert len(state(d)["qa_runs"]) == 1


def test_the_morning_report_lists_per_requirement_merges_fixes_and_parks(repo, gh):
    d = full_spec(repo, "マージまで")
    make_done(repo, d)
    s = state(d)
    s["fails"] = {"R1": [{"from": "reviewer", "evidence": "e", "at": time.time()}]}
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    gh.answers("pr view", [merged_pr(git_head(repo))])
    assert night(repo, "merged", str(d), "--pr", "7").returncode == 0
    r = night(repo, "park", str(d), "--kind", "other", "--op", "Slack に投稿", "--reason", "範囲の外", "--req", "R2")
    assert r.returncode == 0
    out = night(repo, "report", str(d)).stdout
    r1 = next(x for x in out.splitlines() if x.startswith("- R1:"))
    r2 = next(x for x in out.splitlines() if x.startswith("- R2:"))
    assert "PR 7" in r1 and "直した欠陥 1" in r1
    assert "Slack に投稿" in r2 and "done" not in r2


def redispatch(repo, d):
    """評価役の high の後に、同じタスクを実装役にもう一度渡す。"""
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0


def test_handoff_after_a_new_dispatch_requires_a_new_commit(repo):
    d = full_spec(repo)
    make_done(repo, d)
    redispatch(repo, d)  # 実装役が commit せずに「直した」と返した
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "commit が無い" in r.stdout


def test_review_refuses_a_skipped_handoff_after_a_new_dispatch(repo):
    d = full_spec(repo)
    make_done(repo, d)
    redispatch(repo, d)
    r = run(repo, "review", str(d), "--high", "none")
    assert r.returncode != 0 and "handoff" in r.stderr


def test_handoff_refuses_a_rewritten_history_while_a_dispatch_is_open(repo):
    d = full_spec(repo)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True)
    make_done(repo, d)
    redispatch(repo, d)
    subprocess.run([*GIT, "reset", "-q", "--hard", "HEAD~1"], cwd=repo, check=True)
    (repo / "fix.js").write_text("y\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "fix.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "rewritten"], cwd=repo, check=True)
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "祖先" in r.stdout


def test_a_parked_high_can_be_reviewed_again_at_the_same_head_without_a_dispatch(repo):
    d = full_spec(repo)
    make_done(repo, d)
    assert night(repo, "park", str(d), "--kind", "other", "--op", "差分の外の直し", "--reason", "差分の外", "--req", "R1").returncode == 0
    r = run(repo, "review", str(d), "--high", "none")
    assert r.returncode == 0, r.stdout + r.stderr


def dispatched_and_committed(repo):
    """T1 を dispatch し、実装役の commit と [x] を作る（起動の記録だけはまだ書かない）。"""
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    return d


def test_handoff_refuses_when_no_implementer_ran_after_the_dispatch(repo):
    implementer_ran()  # dispatch の前の起動は数えない
    d = dispatched_and_committed(repo)
    implementer_ran("autopilot-implementer", agent_type="general-purpose")  # 実装役でない agent に書かせた
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "autopilot-implementer" in r.stdout and "起動した記録が無い" in r.stdout
    implementer_ran()
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0


def test_handoff_refuses_an_implementer_of_another_rung(repo):
    d = dispatched_and_committed(repo)
    implementer_ran("autopilot-implementer-opus")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "autopilot-implementer-opus" in r.stdout


def test_handoff_refuses_a_model_other_than_the_definition(repo):
    d = dispatched_and_committed(repo)
    implementer_ran(model="claude-opus-5-5")  # model を渡して定義の model より優先させた
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "claude-opus-5-5" in r.stdout and "claude-sonnet-5-5" in r.stdout


def test_handoff_refuses_an_effort_other_than_the_definition(repo):
    d = dispatched_and_committed(repo)
    implementer_ran(effort="xhigh")  # main の effort を継承した
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "effort xhigh で動いた" in r.stdout and "定義は high" in r.stdout


def test_handoff_accepts_an_alias_model_of_the_definition(repo):
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    assert night(repo, "dispatch", str(d), "--task", "T1").returncode == 0
    s = json.loads((d / "state.json").read_text(encoding="utf-8"))
    s["dispatches"][-1]["agent"] = "autopilot-implementer-opus"  # 定義の model は別名の opus
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    implementer_ran("autopilot-implementer-opus", model="claude-opus-5-5")
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0


def test_handoff_refuses_when_the_session_is_unknown(repo):
    """dispatch のときも handoff のときもセッションが分からない（Claude Code の外で動かした）。"""
    d = full_spec(repo)
    (d / "tasks.md").write_text("- [ ] T1: 規則 [R1, R2]\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    cli = [sys.executable, str(OVERNIGHT)]
    assert subprocess.run([*cli, "dispatch", str(d), "--task", "T1"], cwd=repo, env=env, capture_output=True).returncode == 0
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "impl"], cwd=repo, check=True)
    (d / "tasks.md").write_text("- [x] T1: 規則 [R1, R2]\n", encoding="utf-8")
    implementer_ran()
    r = subprocess.run([*cli, "handoff", str(d), "--task", "T1"], cwd=repo, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 1 and "CLAUDE_CODE_SESSION_ID" in r.stdout


def test_handoff_reads_the_model_from_the_transcript_not_the_meta(repo):
    """host の meta.json には model が無いことがあり、transcript には host が足す <synthetic> の行が混ざる。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    meta = max(sub.glob("*.meta.json"), key=lambda p: p.name)
    meta.write_text(json.dumps({"agentType": "spec-autopilot:autopilot-implementer"}), encoding="utf-8")
    with meta.with_name(meta.name[: -len(".meta.json")] + ".jsonl").open("a", encoding="utf-8") as h:
        h.write(json.dumps({"type": "assistant", "message": {"model": "<synthetic>"}}) + "\n")
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0
    redispatch(repo, d)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "fix"], cwd=repo, check=True)
    implementer_ran(model="claude-sonnet-5")  # 定義の ID と違う版で動いた
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "claude-sonnet-5 " in r.stdout



def test_handoff_refuses_a_dispatch_without_an_agent_name(repo):
    d = dispatched_and_committed(repo)
    s = json.loads((d / "state.json").read_text(encoding="utf-8"))
    del s["dispatches"][-1]["agent"]  # 前の版が書いた記録・手で直した記録
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    implementer_ran()
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "名前が無い" in r.stdout


def test_handoff_refuses_an_unreadable_implementer_record(repo):
    """実装役と読めた記録の transcript が壊れていたら、飛ばさずに止める（照合できないまま通さない）。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    (sub / "agent-bad.meta.json").write_text(json.dumps({"agentType": "spec-autopilot:autopilot-implementer"}), encoding="utf-8")
    (sub / "agent-bad.jsonl").write_text('{"type":"user","timestamp":"2099-01-01T00:00:00Z"}\n{"type":"assistant","mess',
                                         encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "agent-bad" in r.stdout and "読めない" in r.stdout


# U+2028・U+2029・U+0085 は生の文字で書かず、エスケープで書く（生で書くと、このファイルを読んだ実装役の transcript が切れる）
LINE_SEPARATORS = ["\u2028", "\u2029", "\x85"]


def implementer_read(text, model=None):
    """implementer_ran() の後に、user の tool_result の行と assistant の行を足す（text は生のまま JSON の文字列に残る）。
    model を渡すと、足す assistant の行だけをその model にする（その行が実際に読まれたかを見分ける）。"""
    log = max((Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents").glob("*.jsonl"), key=lambda f: f.name)
    rows = [{"type": "user", "timestamp": "2099-01-01T00:00:00Z",
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": text}]}},
            {"type": "assistant", "timestamp": "2099-01-01T00:00:00Z", "effort": json.loads(log.read_text(encoding="utf-8").splitlines()[1])["effort"],
             "message": {"model": model or json.loads(log.read_text(encoding="utf-8").splitlines()[1])["message"]["model"],
                         "content": [{"type": "text", "text": text}]}}]
    with log.open("a", encoding="utf-8", newline="") as f:
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    assert text in log.read_bytes().decode("utf-8")  # 生の文字がファイルに残っている


@pytest.mark.parametrize("sep", LINE_SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_handoff_reads_a_record_with_a_line_separator_in_a_string(repo, sep):
    """tool_result の行と assistant の行の文字列に生の改行に似た文字があっても、読めない記録とせず、model・effort・commit で判定する。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    implementer_read(f"読んだ行 a{sep}b 終わり")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("sep", LINE_SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_handoff_judges_the_model_of_a_row_after_a_line_separator(repo, sep):
    """区切り文字を持つ行も読み飛ばさずに判定に使う（その行の model が定義と違えば止める）。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    implementer_read(f"a{sep}b", model="claude-opus-5-5")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "claude-opus-5-5" in r.stdout and "読めない" not in r.stdout


def test_handoff_still_refuses_a_cut_line_in_a_record_with_a_line_separator(repo):
    """生の U+2028 を持つ行と、途中で切れた行が混ざる実装役の記録は、読めない記録として止める。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    (sub / "agent-bad.meta.json").write_text(json.dumps({"agentType": "spec-autopilot:autopilot-implementer"}), encoding="utf-8")
    good = json.dumps({"type": "user", "timestamp": "2099-01-01T00:00:00Z", "message": {"content": "a\u2028b"}}, ensure_ascii=False)
    (sub / "agent-bad.jsonl").write_text(good + '\n{"type":"assistant","mess', encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "agent-bad" in r.stdout and "読めない" in r.stdout


def test_handoff_skips_a_broken_record_of_another_agent(repo):
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-other.meta.json").write_text("{not json", encoding="utf-8")
    (sub / "agent-doc.meta.json").write_text(json.dumps({"agentType": "plain-writing:document-writer"}), encoding="utf-8")
    (sub / "agent-doc.jsonl").write_text('"text"\n', encoding="utf-8")
    d = dispatched_and_committed(repo)
    implementer_ran()
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr


def test_handoff_reads_the_records_of_the_session_that_dispatched(repo):
    """別のセッションが引き継いで handoff を打っても、dispatch したセッションの起動の記録で確かめる。"""
    d = dispatched_and_committed(repo)
    implementer_ran()
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "s2"}
    r = subprocess.run([sys.executable, str(OVERNIGHT), "handoff", str(d), "--task", "T1"], cwd=repo, capture_output=True,
                       text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr




def test_handoff_uses_the_meta_time_when_the_transcript_is_missing(repo):
    """transcript の無い実装役の記録は、meta.json の時刻で dispatch の前か後かを決める。"""
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    sub.mkdir(parents=True)
    old = sub / "agent-old.meta.json"
    old.write_text(json.dumps({"agentType": "spec-autopilot:autopilot-implementer"}), encoding="utf-8")
    os.utime(old, (1, 1))
    d = dispatched_and_committed(repo)
    implementer_ran()
    assert night(repo, "handoff", str(d), "--task", "T1").returncode == 0
    redispatch(repo, d)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "fix"], cwd=repo, check=True)
    implementer_ran()
    (sub / "agent-new.meta.json").write_text(json.dumps({"agentType": "spec-autopilot:autopilot-implementer"}), encoding="utf-8")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 1 and "agent-new" in r.stdout and "agent-old" not in r.stdout


# --- 閉じた後の main のコード（R4・R5・R6） ---

def _g(repo, *args):
    return subprocess.run([*GIT, *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _closed_on_work(repo):
    d = full_spec(repo)
    _g(repo, "commit", "-q", "--allow-empty", "-m", "base")
    base = _g(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _g(repo, "checkout", "-q", "-b", "work")
    make_done(repo, d)
    return d, base


def test_handoff_refuses_code_written_by_main_after_close(repo):
    d, _ = _closed_on_work(repo)
    (repo / "hack.js").write_text("x\n", encoding="utf-8")
    _g(repo, "add", "hack.js")
    _g(repo, "commit", "-q", "-m", "main wrote")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode != 0 and "hack.js" in r.stdout


def test_handoff_passes_after_spec_only_amend_and_integration_merge(repo):
    d, base = _closed_on_work(repo)
    _g(repo, "checkout", "-q", base)
    (repo / "other.txt").write_text("main moved\n", encoding="utf-8")
    _g(repo, "add", "other.txt")
    _g(repo, "commit", "-q", "-m", "main moved")
    _g(repo, "checkout", "-q", "work")
    _g(repo, "merge", "-q", "--no-edit", base)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8") + "\n追記\n", encoding="utf-8")
    _g(repo, "add", "-f", str(d / "spec.md"))
    _g(repo, "commit", "-q", "--amend", "--no-edit")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode == 0, r.stdout + r.stderr


def test_handoff_refuses_when_the_closed_tip_is_unreadable(repo):
    d, _ = _closed_on_work(repo)
    s = state(d)
    s["handoffs"][-1]["tip"] = "0" * 40
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    _g(repo, "commit", "-q", "--allow-empty", "-m", "moved")
    r = night(repo, "handoff", str(d), "--task", "T1")
    assert r.returncode != 0 and "読めない" in r.stdout


def failed_deploy_rows(d, sep, n):
    """sha の m0..m<n-1> のマージごとに、detail に区切り文字を持つ deploy の failure の行を書く（ensure_ascii=False で await と同じ形）。"""
    with (d / "awaits.jsonl").open("w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"kind": "deploy", "pr": 1, "sha": f"m{i}", "result": "failure", "started_at": 1.0,
                                "at": 10.0 + i, "detail": [f"deploy{sep}x: 失敗（run 5）"]}, ensure_ascii=False) + "\n")
    return {"approved_at": 1.0, "merges": [{"sha": f"m{i}"} for i in range(n)]}


@pytest.mark.parametrize("sep", LINE_SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_a_failed_deploy_row_with_a_line_separator_is_counted(tmp_path, sep):
    """待ちの記録の文字列に改行に似た文字があっても、deploy の failure を数え、上限と smoke の判定に効かせる。"""
    import overnight
    s = failed_deploy_rows(tmp_path, sep, overnight.MAX_DEPLOY_FIXES + 1)
    assert overnight.failed_deploys(tmp_path, s) == overnight.MAX_DEPLOY_FIXES + 1
    assert overnight.deploy_exhausted(tmp_path, s)
    assert overnight.deploy_smoke(tmp_path, s) == (True, None)


@pytest.mark.parametrize("bad", ['{"kind": "deploy", "sha": "m0", "res', '[1, 2]', '{"kind": "deploy"}'],
                         ids=["cut", "not-a-dict", "no-at"])
def test_an_unreadable_await_row_stops_with_the_file_and_line(tmp_path, bad):
    """空でないのに記録として読めない行があれば、数えずに通さず、ファイルと行番号を名指しして止める。"""
    import overnight
    s = failed_deploy_rows(tmp_path, " ", 1)
    with (tmp_path / "awaits.jsonl").open("a", encoding="utf-8") as f:
        f.write(bad + "\n")
    with pytest.raises(ValueError, match=r"awaits\.jsonl:2 "):
        overnight.failed_deploys(tmp_path, s)


def test_empty_await_rows_are_not_records(tmp_path):
    """空の行（末尾の改行の後と、書き手が足した改行）は記録ではないので、止めずに飛ばす。"""
    import overnight
    s = failed_deploy_rows(tmp_path, " ", 1)
    with (tmp_path / "awaits.jsonl").open("a", encoding="utf-8") as f:
        f.write("\n\n")
    assert overnight.failed_deploys(tmp_path, s) == 1
