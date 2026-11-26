"""Stop hook が host の timeout（30 秒）より前に、止める側に倒れて判定を出し終えることを確かめる。

- transcript の走査（待ちの判定・異常の知らせ）は、1 回の hook の予算を過ぎたら止める側に倒れる
- transcript は 1 行ずつ読む（本文の U+2028 や \\r で割らない）
- 待ちの poll の照合は command の長さに比例する時間で終わる
- 判定の途中の SystemExit などでも、最初の停止は止め、続行中は放す
"""
import io
import json
import re
import os
import shutil
import subprocess
import sys
import time

import pytest

from test_autopilot import (PLUGIN, alive, approved, launched, later_tool, repo, timer,  # noqa: F401（repo は fixture）
                            transcript)

sys.path.insert(0, str(PLUGIN / "hooks"))
sys.path.insert(0, str(PLUGIN / "scripts"))
import autopilot  # noqa: E402
import stop  # noqa: E402
import transcript as tr  # noqa: E402

PAST = -1.0  # time.monotonic() からの相対。もう過ぎた予算


def expired():
    return time.monotonic() + PAST


def test_scan_raises_when_the_budget_has_passed(tmp_path):
    path = transcript(tmp_path, launched("a1"), *timer())
    with pytest.raises(tr.Overdue):
        stop.scan(path, deadline=expired())


def test_wait_state_falls_to_the_stopping_side_when_the_budget_has_passed(tmp_path):
    """待ち中で timer が生きていても、予算を過ぎたら放さない（None は「待ち中なし」で、止める理由があれば止める）。"""
    path = transcript(tmp_path, launched("a1"), *timer())
    alive(path, "a1")
    assert stop.wait_state({"transcript_path": str(path)}) == "release"
    assert stop.wait_state({"transcript_path": str(path)}, deadline=expired()) is None


def test_wait_state_does_not_ask_ps_after_the_budget(tmp_path):
    path = transcript(tmp_path, launched("a1", ago=300), *timer(ago=0), later_tool())
    alive(path, "a1")
    asked = []
    soon = time.monotonic() + 30
    stop.wait_state({"transcript_path": str(path)}, deadline=soon, processes=lambda timeout=5: asked.append(timeout))
    assert asked and asked[0] <= 5
    asked.clear()
    stop.wait_state({"transcript_path": str(path)}, deadline=time.monotonic() + 0.5,
                    processes=lambda timeout=5: asked.append(timeout))
    assert all(t <= 0.5 for t in asked)


def test_decide_blocks_a_building_spec_once_when_the_budget_has_passed_before_judging(repo):
    d = approved(repo)
    payload = {"cwd": str(repo), "session_id": "s1", "stop_hook_active": False}
    out = stop.decide(autopilot, payload, deadline=expired())
    assert out["decision"] == "block" and d.name in out["reason"]
    again = stop.decide(autopilot, {**payload, "stop_hook_active": True}, deadline=expired())
    assert not again or "decision" not in again


def test_anomalies_raises_when_the_budget_has_passed(tmp_path):
    path = transcript(tmp_path, launched("a1"))
    with pytest.raises(tr.Overdue):
        tr.anomalies(path, since=0, deadline=expired())


def test_the_notice_keeps_what_it_counted_before_the_budget(repo, tmp_path, monkeypatch):
    """spec ごとの知らせは、予算を過ぎた spec の分だけ落とし、数え終えた分は残す。"""
    approved(repo)
    path = transcript(tmp_path, launched("a1"))
    calls = []

    def counted(p, since=None, deadline=None):
        calls.append(1)
        if len(calls) > 1:
            raise tr.Overdue()
        return {"裏で走った agent": 1}

    monkeypatch.setattr(tr, "anomalies", counted)
    monkeypatch.setattr(stop, "recorded", lambda a, p, u: [d for d in autopilot.spec_dirs(repo)] * 2)
    msg = stop.anomaly_notice(autopilot, {"transcript_path": str(path), "session_id": "s1"}, deadline=time.monotonic() + 30)
    assert msg and "裏で走った agent" in msg


def test_scan_reads_lines_with_u2028_and_carriage_returns_inside(tmp_path):
    row = launched("a1")
    row["message"]["content"][0]["content"][0]["text"] += " \r"
    path = transcript(tmp_path, row, *timer())
    agents, timers, _ = stop.scan(path)
    assert "a1" in agents and timers


@pytest.mark.parametrize("cmd,polls", [
    ("while true; do sleep 5; done", True),
    ("until curl -s x; do sleep 10; done", True),
    ("sleep 5; while x; do :; done", False),
    ("awhile sleep 1", False),
    ("while x; do sleepy 1; done", False),
    ("echo while; sleep 1", True),
])
def test_loop_sleep_matches_the_same_commands(cmd, polls):
    assert tr._polls({"command": cmd}) is polls


def test_loop_sleep_ends_quickly_on_a_long_command():
    start = time.monotonic()
    tr._polls({"command": "while " * 200_000})
    assert time.monotonic() - start < 2


@pytest.mark.parametrize("exc", [SystemExit(1), KeyboardInterrupt()], ids=["SystemExit", "KeyboardInterrupt"])
@pytest.mark.parametrize("retry", [False, True], ids=["first-stop", "stop-hook-active"])
def test_main_answers_when_the_judgement_raises_a_base_exception(monkeypatch, capsys, exc, retry):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(stop, "decide", boom)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps({"stop_hook_active": retry}).encode())))
    assert stop.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert ("decision" in out) is (not retry)


# hooks.json の Stop は shell の wrapper（hooks/stop.sh）から stop.py を起動する。stop.py が判定を出さずに
# 終了コード 0 以外で終わったら（シグナルを含む）、wrapper が最初の停止は止め、続行中は放す
def stop_command():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]
    return hooks[0]["hooks"][0]["command"]


def fake_root(tmp_path, body):
    """本物の stop.sh と、偽の stop.py を置いた plugin の root。"""
    (tmp_path / "hooks").mkdir()
    shutil.copy(PLUGIN / "hooks" / "stop.sh", tmp_path / "hooks" / "stop.sh")
    (tmp_path / "hooks" / "stop.py").write_text(body, encoding="utf-8")
    return tmp_path


def run_hook(root, payload):
    return subprocess.run(["sh", "-c", stop_command()], input=json.dumps(payload), capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)}, timeout=30)


KILLED = "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n"


@pytest.mark.parametrize("payload", [{"stop_hook_active": False}, {}], ids=["false", "missing"])
def test_wrapper_blocks_the_first_stop_when_stop_py_dies_by_a_signal(tmp_path, payload):
    r = run_hook(fake_root(tmp_path, KILLED), payload)
    assert r.returncode == 0
    assert json.loads(r.stdout)["decision"] == "block"


def test_wrapper_releases_a_retry_when_stop_py_dies_by_a_signal(tmp_path):
    r = run_hook(fake_root(tmp_path, KILLED), {"stop_hook_active": True})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "decision" not in out and out["systemMessage"]


def test_wrapper_passes_stdin_and_stdout_through(tmp_path):
    body = "import sys, json\nd = json.loads(sys.stdin.read())\nprint(json.dumps({'systemMessage': d['x']}))\n"
    r = run_hook(fake_root(tmp_path, body), {"x": "あ \\" + '"' + " $HOME `id`"})
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"systemMessage": "あ \\" + '"' + " $HOME `id`"}


@pytest.mark.parametrize("code", [1, 2, 127])
@pytest.mark.parametrize("retry", [False, True], ids=["first-stop", "stop-hook-active"])
def test_wrapper_answers_when_stop_py_ends_with_a_failure_code(tmp_path, code, retry):
    """終了コード 0 のときだけ stop.py の答えを返す。ほかは、最初の停止は止め、続行中は放す。"""
    r = run_hook(fake_root(tmp_path, f"import sys\nprint('x')\nsys.exit({code})\n"), {"stop_hook_active": retry})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert ("decision" in out) is (not retry)


def test_wrapper_runs_the_real_stop_py(tmp_path):
    r = subprocess.run(["sh", "-c", stop_command()], input=json.dumps({"cwd": str(tmp_path), "session_id": "none"}),
                       capture_output=True, text=True, env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}, timeout=30)
    assert r.returncode == 0 and r.stdout == ""


def test_host_skips_the_wrapper_shell(tmp_path):
    """wrapper の shell を挟んでも、stop.py の祖先のうち shell でない最初のもの（起動した側）を host にする。"""
    body = (f"import sys\nsys.path.insert(0, {str(PLUGIN / 'hooks')!r})\nsys.path.insert(0, {str(PLUGIN / 'scripts')!r})\n"
            "import stop\nprocs = stop._processes()\nprint(stop._host(procs))\n")
    r = run_hook(fake_root(tmp_path, body), {})
    assert r.stdout.strip() == str(os.getpid())


@pytest.mark.parametrize("retry", [False, True], ids=["first-stop", "stop-hook-active"])
def test_hook_answers_when_autopilot_cannot_be_imported(tmp_path, retry):
    """payload は読めて autopilot.py だけが import できないときは、判定の途中の例外と同じく、最初の停止は止め、続行中は放す。"""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "scripts").mkdir()
    shutil.copy(PLUGIN / "hooks" / "stop.sh", tmp_path / "hooks" / "stop.sh")
    shutil.copy(PLUGIN / "hooks" / "stop.py", tmp_path / "hooks" / "stop.py")
    (tmp_path / "scripts" / "autopilot.py").write_text("raise ImportError('broken')\n", encoding="utf-8")
    r = run_hook(tmp_path, {"stop_hook_active": retry})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out.get("decision") == (None if retry else "block")


def test_stop_py_arms_a_wall_clock_limit_that_the_os_enforces_before_the_host_timeout(tmp_path):
    """判定の途中（正規表現の C の中を含む）で時間が過ぎても、OS が殺して wrapper の止める側に落とす。"""
    probe = ("import runpy, signal, sys\n"
             "real = signal.alarm\n"
             "def spy(sec):\n"
             "    sys.stderr.write(f'alarm={sec} handler={signal.getsignal(signal.SIGALRM) == signal.SIG_DFL}\\n')\n"
             "    return real(sec)\n"
             "signal.alarm = spy\n"
             f"runpy.run_path({str(PLUGIN / 'hooks' / 'stop.py')!r}, run_name='__main__')\n")
    r = subprocess.run([sys.executable, "-c", probe], input="{}", capture_output=True, text=True, cwd=tmp_path, timeout=60)
    m = re.search(r"alarm=(\d+) handler=(\w+)", r.stderr)
    assert m, r.stderr
    assert stop.BUDGET_SEC < int(m.group(1)) < 30 and m.group(2) == "True"


def test_wrapper_blocks_the_first_stop_when_the_wall_clock_limit_kills_stop_py(tmp_path):
    body = "import signal, time\nsignal.alarm(1)\ntime.sleep(10)\n"
    r = run_hook(fake_root(tmp_path, body), {"stop_hook_active": False})
    assert json.loads(r.stdout)["decision"] == "block"
