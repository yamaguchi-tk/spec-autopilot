"""自走の異常（約束から外れた動き）の検知を、入口（Stop hook・`autopilot.py anomalies`・`done`）から通して確かめる。"""
import json
import subprocess
import sys

from test_autopilot import PROMPT, approved, iso, make_done, repo, run, state, stop_hook, transcript  # noqa: F401（repo は fixture）


def say(text, ago=30):
    return {"type": "user", "timestamp": iso(ago), "message": {"role": "user", "content": text}}


def reply(text="続けます", ago=30, stop="end_turn"):
    return {"type": "assistant", "timestamp": iso(ago), "message": {"role": "assistant", "stop_reason": stop,
                                                                     "content": [{"type": "text", "text": text}]}}


def tool(name, inp, ago=30, tid="toolu_x"):
    return {"type": "assistant", "timestamp": iso(ago), "message": {"role": "assistant", "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid="toolu_x", text="ok", ago=30):
    return {"type": "user", "timestamp": iso(ago), "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text}]}}


FEEDBACK = "Stop hook feedback:\n自走中の spec が完了の検査を通っていない。"


def feedback(ago=20):
    """Stop hook の押し返しは、host が isMeta の user の行で記録する（実際の transcript の形）。"""
    return {**say(FEEDBACK, ago=ago), "isMeta": True}


def empty_blocks(n, ago=20):
    """ago が負なら、承認より後（未来）の時刻にする（Stop hook は承認の時刻より後だけを数える）。"""
    rows = []
    for _ in range(n):
        rows += [reply(ago=ago), feedback(ago)]
    return rows


def approve_rows(budget=30, ago=60):
    return [tool("Bash", {"command": 'python3 "$P/autopilot.py" approve docs/specs/x --by OK'}, ago=ago, tid="toolu_ap"),
            result("toolu_ap", f"approved: 予算 {budget} 分。ここから自走する", ago=ago)]


def anomalies(repo, *paths):
    r = run(repo, "anomalies", *map(str, paths))
    assert r.returncode == 0, r.stderr
    return r.stdout


def hook(repo, path):
    r = stop_hook(repo, {"transcript_path": str(path)})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else {}


# --- 型ごとの数え方（CLI） ---

def test_cli_counts_three_empty_blocks_in_a_row_once(repo, tmp_path):
    path = transcript(tmp_path, *approve_rows(), *empty_blocks(5))
    assert "空の turn の block 1" in anomalies(repo, path)


def test_cli_does_not_count_blocks_after_turns_that_called_tools(repo, tmp_path):
    rows = []
    for i in range(4):
        rows += [tool("Read", {"file_path": f"/a{i}"}, tid=f"t{i}"), result(f"t{i}"), reply(), feedback()]
    path = transcript(tmp_path, *approve_rows(), *rows, *empty_blocks(2))
    assert "空の turn の block 0" in anomalies(repo, path)


def test_cli_counts_asking_the_human_after_approve(repo, tmp_path):
    path = transcript(tmp_path, *approve_rows(),
                      tool("AskUserQuestion", {"questions": []}, tid="q1"), result("q1"),
                      reply("どちらにしますか？"), say("A で"))
    assert "承認後に人へ問い 2" in anomalies(repo, path)


def test_cli_does_not_count_hook_feedback_compaction_or_notifications_as_the_human(repo, tmp_path):
    path = transcript(tmp_path, *approve_rows(), reply(), feedback(),
                      reply(), say("This session is being continued from a previous conversation"),
                      reply(), say("<task-notification>\n<status>completed</status>\n</task-notification>"))
    assert "承認後に人へ問い 0" in anomalies(repo, path)


def test_cli_counts_polling_but_not_the_wake_up_timer_or_short_sleeps(repo, tmp_path):
    path = transcript(tmp_path, *approve_rows(),
                      tool("Bash", {"command": "until grep -q done tasks.md; do sleep 5; done"}, tid="p1"),
                      tool("Bash", {"command": "sleep 120"}, tid="p2"),
                      tool("Bash", {"command": "sleep 900", "run_in_background": True}, tid="p3"),
                      tool("Bash", {"command": "(python3 -m http.server &); sleep 1; curl localhost"}, tid="p4"),
                      tool("Bash", {"command": "until [ -f done ]; do sleep 5; done", "run_in_background": True}, tid="p5"))
    assert "待ちの poll 3" in anomalies(repo, path)


def test_cli_counts_only_between_approve_and_done(repo, tmp_path):
    before = [tool("AskUserQuestion", {"questions": []}, tid="q0")]
    after = [tool("Bash", {"command": 'python3 autopilot.py done docs/specs/x'}, tid="dn"),
             result("dn", "done: 承認から 5.0 分（確認待ちを除く）"), tool("AskUserQuestion", {"questions": []}, tid="q2")]
    path = transcript(tmp_path, *before, *approve_rows(), tool("AskUserQuestion", {"questions": []}, tid="q1"), *after)
    assert "承認後に人へ問い 1" in anomalies(repo, path)


def test_cli_skips_transcripts_without_approve(repo, tmp_path):
    path = transcript(tmp_path, tool("AskUserQuestion", {"questions": []}, tid="q1"))
    assert "承認なし" in anomalies(repo, path)


def test_cli_ignores_subagent_records(repo, tmp_path):
    side = tool("Bash", {"command": "sleep 60"}, tid="s1")
    side["isSidechain"] = True
    path = transcript(tmp_path, *approve_rows(), side)
    assert "待ちの poll 0" in anomalies(repo, path)


# --- Stop hook: 知らせるだけ（止める・放すは変えない） ---

def test_stop_hook_notifies_a_new_anomaly_without_changing_the_block(repo, tmp_path):
    d = approved(repo)
    path = transcript(tmp_path, *empty_blocks(3, ago=-2))
    out = hook(repo, path)
    assert out["decision"] == "block"
    assert "異常" in out["systemMessage"] and "空の turn の block" in out["systemMessage"]
    assert state(d)["anomalies"]["空の turn の block"] == 1


def test_stop_hook_notifies_each_anomaly_only_once(repo, tmp_path):
    approved(repo)
    path = transcript(tmp_path, *empty_blocks(3, ago=-2))
    hook(repo, path)
    assert "systemMessage" not in hook(repo, path)


def test_stop_hook_counts_only_after_the_recorded_approve(repo, tmp_path):
    approved(repo)
    path = transcript(tmp_path, tool("AskUserQuestion", {"questions": []}, ago=3600, tid="q0"))
    assert "systemMessage" not in hook(repo, path)


def test_stop_hook_keeps_the_decision_when_the_transcript_cannot_be_read(repo, tmp_path):
    approved(repo)
    out = hook(repo, tmp_path)  # ディレクトリは読めない
    assert out["decision"] == "block" and "systemMessage" not in out


def test_stop_hook_does_not_notify_after_done(repo, tmp_path):
    d = approved(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    path = transcript(tmp_path, *empty_blocks(3, ago=-2))
    assert hook(repo, path) == {}


# --- done: 記録した異常の件数を出す ---

def test_done_reports_the_recorded_anomalies(repo, tmp_path):
    d = approved(repo)
    hook(repo, transcript(tmp_path, *empty_blocks(3, ago=-2)))
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "異常: 空の turn の block 1" in r.stdout


def test_done_reports_no_anomalies(repo):
    d = approved(repo)
    make_done(repo, d)
    assert "異常: なし" in run(repo, "done", str(d)).stdout


# --- 型 2: 前景のはずの agent が裏で走った（Agent の結果が async_launched） ---

def launched_as(tid, background, ago=30):
    inp = {"description": "実装", "prompt": "T1", "subagent_type": "spec-autopilot:autopilot-implementer"}
    if background is not None:
        inp["run_in_background"] = background
    res = {**result(tid, "Async agent launched successfully.", ago=ago),
           "toolUseResult": {"isAsync": True, "status": "async_launched", "agentId": "a1"}}
    return [tool("Agent", inp, ago=ago, tid=tid), res]


def test_cli_counts_every_agent_that_ran_in_the_background(repo, tmp_path):
    path = transcript(tmp_path, *approve_rows(), *launched_as("g1", None), *launched_as("g2", True), *launched_as("g3", False))
    assert "裏で走った agent 3" in anomalies(repo, path)  # false を明示しても裏で走れば数える


def on_desktop(rows):
    """Claude Desktop の transcript は、行に entrypoint: claude-desktop を持つ（Desktop は前景を選べない）。"""
    return [{**r, "entrypoint": "claude-desktop"} for r in rows]


def test_cli_does_not_count_an_agent_launched_as_foreground_on_desktop(repo, tmp_path):
    """Desktop では false を明示しても必ず裏で走るので、false を明示したものは数えない。明示しなかったもの・true は数える。"""
    path = transcript(tmp_path, *approve_rows(),
                      *on_desktop(launched_as("g1", False)), *on_desktop(launched_as("g2", None)), *on_desktop(launched_as("g3", True)))
    assert "裏で走った agent 2" in anomalies(repo, path)


def test_cli_reads_the_string_false_that_desktop_records(repo, tmp_path):
    """Desktop の transcript は run_in_background を文字列（"false"・"true"）で残す（実測 198 件・255 件、bool は 0 件）。"""
    path = transcript(tmp_path, *approve_rows(),
                      *on_desktop(launched_as("g1", "false")), *on_desktop(launched_as("g2", "true")))
    assert "裏で走った agent 1" in anomalies(repo, path)


def test_cli_does_not_count_the_human_reply_while_waiting(repo, tmp_path):
    """wait（1 操作ごとの確認）の後の人の返事は、resume までは問いに数えない。resume の後の返事は数える。"""
    wait = [tool("Bash", {"command": 'python3 autopilot.py wait docs/specs/x --reason "apply"'}, tid="w1"),
            result("w1", "wait: 確認を人に 1 通で示す。返事を受けたら resume で戻る")]
    resume = [tool("Bash", {"command": "python3 autopilot.py resume docs/specs/x"}, tid="r1"), result("r1", "resume: 自走に戻る")]
    path = transcript(tmp_path, *approve_rows(), *wait, reply("apply してよいですか？"), say("OK"),
                      *resume, reply("どちらにしますか？"), say("A で"))
    assert "承認後に人へ問い 1" in anomalies(repo, path)


def test_cli_does_not_count_a_foreground_agent(repo, tmp_path):
    fg = [tool("Agent", {"prompt": "T1"}, tid="g1"), result("g1", "done")]
    path = transcript(tmp_path, *approve_rows(), *fg)
    assert "裏で走った agent 0" in anomalies(repo, path)


# --- done: 最後の turn（building の停止が無い間）の異常も数える ---

def prompt_with_transcript(repo, path, session="s1"):
    """人の発言を UserPromptSubmit hook に通す。host の payload と同じく transcript_path を入れる。"""
    r = subprocess.run([sys.executable, str(PROMPT)], capture_output=True, text=True, cwd=repo,
                       input=json.dumps({"cwd": str(repo), "prompt": "OK", "session_id": session, "transcript_path": str(path)}))
    assert r.returncode == 0, r.stderr


def test_done_counts_the_transcript_up_to_done_even_without_a_stop_in_between(repo, tmp_path):
    path = transcript(tmp_path)
    d = approved(repo)  # approved() の人の発言は transcript_path を持たないので、その後の発言で記録する
    prompt_with_transcript(repo, path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tool("Bash", {"command": "sleep 120"}, ago=-2, tid="p1"), ensure_ascii=False) + "\n")
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "異常: 待ちの poll 1" in r.stdout
