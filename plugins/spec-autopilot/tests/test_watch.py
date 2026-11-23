"""セッションの外の見回り役（watch.py）を、入口（watch.py の CLI・Stop hook・SessionStart hook）から確かめる。
claude と osascript は PATH の先頭に置いた偽物で、引数と cwd を記録する。"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_autopilot import PLUGIN, approved, init_spec, make_done, repo, run, state, stop_hook, user_says  # noqa: F401

WATCH = PLUGIN / "scripts" / "watch.py"
START = PLUGIN / "hooks" / "session_start.py"
FAKE = """#!/bin/sh
printf '%s\\n' "$(pwd)" "$@" > "{log}/{name}.$$.log"
{tail}
"""


@pytest.fixture
def bin_dir(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (tmp_path / "calls").mkdir()
    for name, tail in (("claude", 'echo \'{"type":"result","is_error":false,"result":"ok"}\''), ("osascript", "")):
        f = b / name
        f.write_text(FAKE.format(log=tmp_path / "calls", name=name, tail=tail), encoding="utf-8")
        f.chmod(0o755)
    return b


def home():
    return Path(os.environ["SPEC_AUTOPILOT_HOME"])


def calls(bin_dir, name):
    time.sleep(0.3)  # 起こした claude は新しい process group で動く
    out = []
    for f in sorted((bin_dir.parent / "calls").glob(f"{name}.*.log")):
        out.append(f.read_text(encoding="utf-8").splitlines())
    return out


def watch(bin_dir, *args):
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    return subprocess.run([sys.executable, str(WATCH), *(args or ("tick",))], capture_output=True, text=True, env=env,
                          timeout=60)


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def started_of(pid):
    out = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)], capture_output=True, text=True).stdout
    days, _, rest = out.strip().rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    sec = parts[-1] + (parts[-2] * 60 if len(parts) > 1 else 0) + (parts[-3] * 3600 if len(parts) > 2 else 0)
    return time.time() - sec - (int(days) * 86400 if days else 0)


def host(repo, session="s1", pid=None, started=None, mode="auto", age=3600, transcript=None):
    """セッションの host の記録（hook が書くもの）を置く。transcript は age 秒前に書かれたことにする。"""
    t = transcript or (repo.parent / f"{session}.jsonl")
    t.write_text("{}\n", encoding="utf-8")
    os.utime(t, (time.time() - age, time.time() - age))
    pid = dead_pid() if pid is None else pid
    rec = {"pid": pid, "started": time.time() - 10 if started is None else started, "mode": mode,
           "cwd": str(repo), "transcript": str(t), "at": time.time() - age}
    f = home() / "sessions" / f"{session}.host.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec), encoding="utf-8")
    return rec


def set_state(d, **kv):
    s = state(d)
    s.update(kv)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")


# --- 起こす ---

def test_wakes_a_session_whose_host_died_while_a_spec_is_building(repo, bin_dir):
    d = approved(repo)
    host(repo)
    r = watch(bin_dir)
    assert r.returncode == 0, r.stdout + r.stderr
    [c] = calls(bin_dir, "claude")
    assert c[0] == str(repo.resolve()) or c[0] == str(repo)
    assert c[1:3] == ["-p", "--resume=s1"] and "autopilot.py status" in c[3]
    assert c[c.index("--permission-mode") + 1] == "auto"
    assert state(d)["phase"] == "building"


def test_wakes_a_session_with_queued_specs_and_nothing_building(repo, bin_dir):
    a = init_spec(repo, "a")
    user_says(repo)
    assert run(repo, "approve", str(a), "--by", "OK", "--queue").returncode == 0
    host(repo)
    watch(bin_dir)
    assert len(calls(bin_dir, "claude")) == 1


@pytest.mark.parametrize("session", ["--dangerously-skip-permissions", "-x", ".hidden", "a b"])
def test_does_not_wake_a_session_whose_id_is_not_a_plain_name(repo, bin_dir, session):
    """session id はファイル名から取るので、先頭が英数字の名前だけを claude の引数にする（option と読まれないように）。"""
    d = approved(repo)
    (home() / "sessions" / f"{session}.json").write_text(json.dumps([str(d.resolve())]), encoding="utf-8")
    host(repo, session=session)
    r = watch(bin_dir)
    assert r.returncode == 0, r.stderr
    assert all(f"--resume={session}" not in c and session not in c for c in calls(bin_dir, "claude"))



def age_spec(d, sec):
    for f in [d, *d.iterdir()]:
        os.utime(f, (time.time() - sec, time.time() - sec))


def test_reports_a_stopped_session_whose_host_was_never_recorded(repo, bin_dir):
    """host の記録が無い（この版より前に始まった・SessionStart で取り損ねた）セッションも、止める spec が長く動いていなければ
    起こさずに報告する（依頼の「再開できなければ朝の報告を書く」）。"""
    d = approved(repo)
    assert (home() / "sessions" / "s1.json").is_file() and not (home() / "sessions" / "s1.host.json").exists()
    age_spec(d, 40 * 60)
    r = watch(bin_dir)
    assert r.returncode == 0, r.stderr
    assert calls(bin_dir, "claude") == []
    assert "host の記録が無い" in (d / "watch-report.md").read_text(encoding="utf-8")


def test_does_not_report_a_session_without_a_host_record_while_its_spec_is_moving(repo, bin_dir):
    d = approved(repo)
    age_spec(d, 5 * 60)
    r = watch(bin_dir)
    assert r.returncode == 0, r.stderr
    assert not (d / "watch-report.md").exists()

def test_reports_without_waking_a_session_whose_host_is_alive_but_silent(repo, bin_dir):
    """host が生きたまま（利用の上限など）長く書かれていない run は、二重に書かないよう起こさずに報告する。"""
    d = approved(repo)
    host(repo, pid=os.getpid(), started=started_of(os.getpid()), age=40 * 60)
    r = watch(bin_dir)
    assert r.returncode == 0, r.stderr
    assert calls(bin_dir, "claude") == []
    assert "動いていない" in (d / "watch-report.md").read_text(encoding="utf-8")


def test_reports_when_the_wake_cannot_start_claude(repo, bin_dir):
    d = approved(repo)
    (bin_dir / "claude").unlink()
    host(repo)
    env_path = f"{bin_dir}:/usr/bin:/bin"
    r = subprocess.run([sys.executable, str(WATCH), "tick"], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "PATH": env_path})
    assert r.returncode == 0, r.stderr
    assert "起動できない" in (d / "watch-report.md").read_text(encoding="utf-8")


# --- 起こさない ---

def test_does_not_wake_while_the_host_is_alive(repo, bin_dir):
    approved(repo)
    host(repo, pid=os.getpid(), started=started_of(os.getpid()))
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


def test_does_not_wake_a_session_written_recently(repo, bin_dir):
    approved(repo)
    host(repo, age=60)
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


@pytest.mark.parametrize("phase", ["done", "blocked", "wait"])
def test_does_not_wake_a_session_the_stop_hook_would_let_go(repo, bin_dir, phase):
    d = approved(repo)
    set_state(d, phase=phase, wait={"reason": "確認", "at": time.time()} if phase == "wait" else None)
    host(repo)
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


def test_does_not_wake_a_spec_past_twice_its_budget(repo, bin_dir):
    d = approved(repo)
    set_state(d, approved_at=time.time() - 6 * 3600)
    host(repo)
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


def test_does_not_wake_a_spec_that_passes_its_check(repo, bin_dir):
    d = approved(repo)
    make_done(repo, d)
    host(repo)
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


def test_does_not_wake_while_a_machine_wait_is_alive(repo, bin_dir):
    d = approved(repo)
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "overnight.py", "await", str(d)])
    try:
        (d / "await.json").write_text(json.dumps({"pid": p.pid, "started_at": time.time(), "deadline": time.time() + 600,
                                                   "dir": str(d)}), encoding="utf-8")
        host(repo)
        watch(bin_dir)
        assert calls(bin_dir, "claude") == []
    finally:
        p.kill()


def test_does_not_wake_when_another_session_with_the_spec_is_alive(repo, bin_dir):
    d = approved(repo)
    host(repo)
    other = home() / "sessions" / "s2.json"
    other.write_text(json.dumps([str(d.resolve())]), encoding="utf-8")
    host(repo, session="s2", pid=os.getpid(), started=started_of(os.getpid()))
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []


@pytest.mark.parametrize("mode", ["default", "plan", None, "bypassPermissions"])
def test_reports_instead_of_waking_when_the_mode_is_not_one_to_pass(repo, bin_dir, mode):
    d = approved(repo)
    host(repo, mode=mode)
    watch(bin_dir)
    assert calls(bin_dir, "claude") == []
    assert "権限" in (d / "watch-report.md").read_text(encoding="utf-8")
    assert len(calls(bin_dir, "osascript")) == 1


def test_reports_after_three_wakes_without_progress(repo, bin_dir):
    d = approved(repo)
    for _ in range(4):
        host(repo)
        watch(bin_dir)
    assert len(calls(bin_dir, "claude")) == 3
    assert "3 回" in (d / "watch-report.md").read_text(encoding="utf-8")
    host(repo)
    watch(bin_dir)  # 報告の後は、進むまで起こさず、知らせも繰り返さない
    assert len(calls(bin_dir, "claude")) == 3 and len(calls(bin_dir, "osascript")) == 1


def test_a_wake_that_hit_the_usage_limit_is_not_counted(repo, bin_dir):
    approved(repo)
    (bin_dir / "claude").write_text((bin_dir / "claude").read_text(encoding="utf-8").replace(
        '"is_error":false', '"is_error":true,"api_error_status":429'), encoding="utf-8")
    for _ in range(5):
        host(repo)
        watch(bin_dir)
        time.sleep(0.3)
    assert len(calls(bin_dir, "claude")) == 5


def test_progress_resets_the_count(repo, bin_dir):
    d = approved(repo)
    for i in range(5):
        host(repo)
        watch(bin_dir)
        (repo / f"f{i}").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", f"c{i}"], cwd=repo, check=True)
    assert len(calls(bin_dir, "claude")) == 5 and not (d / "watch-report.md").exists()


# --- hook が host を記録する ---

def session_start(repo, session="s1", source="startup", **extra):
    data = {"cwd": str(repo), "session_id": session, "source": source, **extra}
    return subprocess.run([sys.executable, str(START)], input=json.dumps(data), capture_output=True, text=True, cwd=repo)


def test_session_start_records_the_host_even_before_the_session_takes_over_a_spec(repo):
    """host が決まるのは SessionStart（startup・resume）なので、自走の記録より前の最初の startup でも書く。"""
    session_start(repo, session="s9", transcript_path=str(repo.parent / "t.jsonl"))
    rec = json.loads((home() / "sessions" / "s9.host.json").read_text(encoding="utf-8"))
    assert rec["pid"] > 1 and rec["cwd"] == str(repo) and rec["transcript"] == str(repo.parent / "t.jsonl")


def test_stop_hook_does_not_look_for_the_host(repo):
    """Stop hook は判定の予算の外で ps を回さない。host.json が無ければ何も書かない。"""
    approved(repo)
    stop_hook(repo, {"permission_mode": "auto"})
    assert not (home() / "sessions" / "s1.host.json").exists()


def test_stop_hook_adds_the_permission_mode_and_keeps_the_host(repo):
    approved(repo)
    session_start(repo)
    f = home() / "sessions" / "s1.host.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    f.write_text(json.dumps({**rec, "pid": 424242, "started": 1.0}), encoding="utf-8")
    stop_hook(repo, {"permission_mode": "acceptEdits", "transcript_path": str(repo.parent / "t2.jsonl")})
    rec = json.loads(f.read_text(encoding="utf-8"))
    assert (rec["pid"], rec["started"], rec["mode"]) == (424242, 1.0, "acceptEdits")
    assert rec["transcript"] == str(repo.parent / "t2.jsonl")


def test_session_start_records_the_host_and_keeps_the_mode(repo):
    approved(repo)
    session_start(repo)
    stop_hook(repo, {"permission_mode": "auto"})
    session_start(repo, source="resume", transcript_path=str(repo.parent / "t.jsonl"))
    assert json.loads((home() / "sessions" / "s1.host.json").read_text(encoding="utf-8"))["mode"] == "auto"


def test_stop_hook_still_blocks_when_the_host_cannot_be_recorded(repo):
    approved(repo)
    (home() / "sessions" / "s1.host.json").mkdir(parents=True)  # 書けない
    out = json.loads(stop_hook(repo).stdout)
    assert out["decision"] == "block"


def test_the_watcher_does_not_write_the_spec_state(repo, bin_dir):
    d = approved(repo)
    host(repo)
    before = (d / "state.json").read_text(encoding="utf-8")
    watch(bin_dir)
    assert (d / "state.json").read_text(encoding="utf-8") == before


# --- 報告を示す・入れ方 ---

def test_session_start_shows_the_watch_report(repo, bin_dir):
    d = approved(repo)
    host(repo, mode="default")
    watch(bin_dir)
    data = {"cwd": str(repo), "session_id": "s1", "source": "startup"}
    r = subprocess.run([sys.executable, str(START)], input=json.dumps(data), capture_output=True, text=True, cwd=repo)
    assert str(d / "watch-report.md") in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_plist_runs_the_tick_every_quarter_hour_in_its_own_process_group(bin_dir):
    r = watch(bin_dir, "plist")
    assert r.returncode == 0
    for word in (str(WATCH), "<string>tick</string>", "<integer>900</integer>", "AbandonProcessGroup", "PATH"):
        assert word in r.stdout


def test_preflight_notes_a_missing_watcher(tmp_path, monkeypatch):
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import preflight

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert any("見回り役" in w for w in preflight.watcher())
    agents = tmp_path / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.spec-autopilot.watch.plist").write_text(subprocess.run(
        [sys.executable, str(WATCH), "plist"], capture_output=True, text=True).stdout, encoding="utf-8")
    assert preflight.watcher() == []
    (agents / "com.spec-autopilot.watch.plist").write_text("<string>/nowhere/watch.py</string>", encoding="utf-8")
    assert any("見回り役" in w for w in preflight.watcher())
