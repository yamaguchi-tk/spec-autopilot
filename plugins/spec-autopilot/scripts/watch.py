#!/usr/bin/env python3
"""セッションの外の見回り役（PR 6.5）。止まった run を同じ session id で起こし直し、起こせなければ報告を残す。

  watch.py tick    見回りを 1 回（launchd が 15 分ごとに起動する）
  watch.py plist   launchd の plist を出す（入れるのは人。commands/autopilot.md の夜通しの前提）

- 起こすのは、セッションを動かしていた host（hook の祖先の claude のプロセス）が死んだときだけ。host が生きたまま
  SILENT_SEC 書かれていない run は、二重に書かないよう起こさずに報告する。host の pid と開始時刻は SessionStart が
  `sessions/<id>.host.json` に書き（record_host）、Stop hook は ps を呼ばずに権限の mode を書き足す（note_stop）。
  host の記録が無いセッションは、止める spec が SILENT_SEC 書かれていなければ起こさずに報告する
- 起こすのは、Stop hook がそのとき止める判定になるセッションだけ（stop.judge を書き込みなしで、stop.lineup_demand を使い回す）
- 起こさないのは: host が生きている・transcript が QUIET_SEC 以内に書かれた・機械の待ち（overnight.py await）が生きている・
  同じ spec を記録した別のセッションの host が生きている
- 権限の mode は host が記録したものを渡す。MODES に無い・読めないときは起こさずに報告する（-p の default は問いを拒んで続け、
  Stop hook が止め続けて費用を使う）
- 進み（spec の phase と repo の HEAD）の無い起こしが続けて MAX_WAKES 回になったら、起こさずに報告する。利用の上限で返った起こしは数えない
- spec の state.json には書かない。見回り役の記録は `watch/<id>.json` に置く。報告は spec のディレクトリの watch-report.md と
  デスクトップ通知に出し、SessionStart が示す
"""
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "hooks"))

MODES = ("auto", "acceptEdits")
QUIET_SEC = 10 * 60
SILENT_SEC = 30 * 60  # host が生きたまま、これより長く書かれていない run は報告する（Bash の前景の上限 10 分より長く）
MAX_WAKES = 3
LABEL = "com.spec-autopilot.watch"
REPORT = "watch-report.md"
PROMPT = ("spec-autopilot の見回り役が、止まっていたこのセッションを起こした（Claude アプリの再起動など）。"
          "autopilot.py status で状態を読み、/autopilot の C の手順で人に聞かずに続ける。"
          "この起動は headless（claude -p）で、turn を終えるとプロセスが終わり、background の Bash・agent も消える。"
          "待ちは前景で回す（Bash の timeout を付けて overnight.py await を繰り返す）。")


def home():
    return Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot")


def host_file(session):
    """host の記録の場所。session id が受理集合（autopilot.SESSION_ID）に合わなければ None。"""
    import autopilot

    f = autopilot.session_file(session)
    return f.with_name(f"{session}.host.json") if f else None


def load(f):
    try:
        v = json.loads(Path(f).read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def save(f, data):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def record_host(payload):
    """SessionStart から呼ぶ。host（hook の祖先の claude のプロセス）が決まるのは startup・resume なので、
    自走の記録の有無によらず、このときだけ pid と開始時刻を書く（ps は SessionStart の予算の内）。"""
    import stop

    session = payload.get("session_id")
    f = host_file(session)
    if f is None:
        return
    procs = stop._processes(timeout=3)
    pid = stop._host(procs) if procs else None
    if pid is None:
        return
    old = load(f)
    save(f, {"pid": pid, "started": time.time() - procs[pid][1], "mode": payload.get("permission_mode") or old.get("mode"),
             "cwd": payload.get("cwd"), "transcript": payload.get("transcript_path") or old.get("transcript"), "at": time.time()})


def note_stop(payload, deadline):
    """Stop hook から呼ぶ。ps は呼ばず、host の記録があるときだけ権限の mode と transcript を書き足す。予算を過ぎていれば書かない。"""
    f = host_file(payload.get("session_id"))
    if f is None or time.monotonic() >= deadline or not f.is_file():
        return
    rec = load(f)
    if not rec:
        return
    save(f, {**rec, "mode": payload.get("permission_mode") or rec.get("mode"),
             "transcript": payload.get("transcript_path") or rec.get("transcript"), "at": time.time()})


def alive(pid, started):
    """pid が生きていて、開始時刻が記録と合うか（pid の再利用を数えない）。ps が使えなければ生きているとみなす（起こさない側）。"""
    import stop

    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
        return False
    try:
        out = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return True
    if out.returncode != 0 or not out.stdout.strip():
        return False
    try:
        return abs(time.time() - stop._elapsed(out.stdout) - float(started)) <= 5
    except (TypeError, ValueError):
        return True


def quiet(rec, sec=QUIET_SEC):
    """transcript と subagent の transcript が sec 秒より前から書かれていないか。"""
    t = rec.get("transcript")
    if not isinstance(t, str):
        return True
    t = Path(t)
    files = [t, *t.with_suffix("").joinpath("subagents").glob("*.jsonl")]
    newest = max((f.stat().st_mtime for f in files if f.exists()), default=0)
    return time.time() - newest > sec


def specs_quiet(specs, sec):
    """spec のディレクトリ（state.json・tasks.md など）が sec 秒より前から書かれていないか。"""
    newest = 0
    for d in specs:
        try:
            newest = max([newest, d.stat().st_mtime, *(f.stat().st_mtime for f in d.iterdir())])
        except OSError:
            continue
    return time.time() - newest > sec


def awaiting(overnight, d):
    """機械の待ち（overnight.py await）のプロセスが、期限の前で生きているか（host の子孫かは見ない）。"""
    rec = overnight.await_record(d)
    if rec is None or time.time() >= rec["deadline"]:
        return False
    try:
        out = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(rec["pid"])], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return True
    return out.returncode == 0 and "await" in out.stdout


def reasons(ap, session):
    """Stop hook がこのセッションを止める理由（書き込みなしで判定する）。"""
    import stop

    found = []
    for d in ap.recorded_specs(session):
        try:
            if ap.load_state(d).get("phase") == "building":
                why, _ = stop.judge(ap, d, record=False)
                if why:
                    found.append(why)
        except Exception:
            continue  # 読めない spec では起こさない（人が見る）
    if not found:
        try:
            nxt = stop.lineup_demand(ap, {"session_id": session})
        except Exception:
            nxt = None
        if nxt:
            found.append(nxt)
    return found


def others_alive(ap, session, specs):
    """同じ spec を記録した別のセッションの host が生きているか。"""
    mine = {str(d.resolve()) for d in specs}
    for f in (home() / "sessions").glob("*.json"):
        other = f.stem
        if other == session or host_file(other) is None:  # .host.json と受理集合の外の id を飛ばす
            continue
        try:
            theirs = {str(d.resolve()) for d in ap.recorded_specs(other)}
        except Exception:
            continue
        if mine & theirs:
            rec = load(host_file(other))
            if alive(rec.get("pid"), rec.get("started")):
                return True
    return False


def signature(ap, specs):
    sig = []
    for d in specs:
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ap.repo_root(d), capture_output=True, text=True,
                                  timeout=30).stdout.strip()
            sig.append([str(d), ap.load_state(d).get("phase"), head])
        except Exception:
            sig.append([str(d), None, None])
    return sig


def limited(log):
    """前の起こしが利用の上限・API の失敗で返ったか（数えない）。"""
    try:
        m = re.search(r"\{.*\}", Path(log).read_text(encoding="utf-8", errors="replace"), re.S)
        v = json.loads(m.group(0)) if m else {}
    except (OSError, ValueError, TypeError):
        return False
    return bool(v.get("is_error")) or bool(v.get("api_error_status"))


def report(ap, session, specs, why, w):
    """起こせない理由を spec のディレクトリに残し、デスクトップに知らせる。同じ理由では繰り返さない。"""
    if w.get("reported") == why:
        return
    stamp = time.strftime("%Y-%m-%d %H:%M")
    for d in specs:
        try:
            if ap.load_state(d).get("phase") in ("done",):
                continue
            with open(d / REPORT, "a", encoding="utf-8") as f:
                f.write(f"- {stamp}（セッション {session}）: {why}\n")
        except Exception:
            continue
    try:
        msg = f"spec-autopilot の見回り役: {why}"
        subprocess.run(["osascript", "-e", f"display notification {json.dumps(msg)} with title \"spec-autopilot\""],
                       capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass
    w["reported"] = why


def wake(session, rec, w):
    log = home() / "watch" / f"{session}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as out:
        p = subprocess.Popen(["claude", "-p", f"--resume={session}", PROMPT, "--permission-mode", rec["mode"],
                              "--output-format", "json"], cwd=rec["cwd"], stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    save(host_file(session), {**rec, "pid": p.pid, "started": time.time(), "at": time.time()})  # 次の見回りが二重に起こさない
    w["log"] = str(log)


def tick_one(ap, overnight, session):
    rec = load(host_file(session))
    specs = ap.recorded_specs(session)
    if not specs:
        return
    if not rec:  # host の記録が無い（この版より前に始まった・SessionStart で取り損ねた）。起こせないので報告だけする
        if specs_quiet(specs, SILENT_SEC) and reasons(ap, session) and not any(awaiting(overnight, d) for d in specs) \
                and not others_alive(ap, session, specs):
            wf = home() / "watch" / f"{session}.json"
            w = load(wf)
            report(ap, session, specs, f"host の記録が無いので起こせない。spec が {SILENT_SEC // 60} 分動いていない。止まっていればセッションを開いて続ける", w)
            save(wf, w)
        return
    living = alive(rec.get("pid"), rec.get("started"))
    if not quiet(rec, SILENT_SEC if living else QUIET_SEC):
        return
    if not reasons(ap, session) or any(awaiting(overnight, d) for d in specs) or others_alive(ap, session, specs):
        return
    wf = home() / "watch" / f"{session}.json"
    w = load(wf)
    if living:  # 起こすと同じセッションに 2 つ書くので、起こさずに報告する（利用の上限で止まった run など）
        report(ap, session, specs, f"セッションは開いているが {SILENT_SEC // 60} 分動いていない（利用の上限など）。セッションを開いて続ける", w)
        save(wf, w)
        return
    sig = signature(ap, specs)
    if w.get("sig") != sig:
        w = {"sig": sig, "n": 0}
    elif w.get("log") and limited(w["log"]):
        w["n"] = max(0, int(w.get("n", 0)) - 1)
    if rec.get("mode") not in MODES:
        report(ap, session, specs, f"権限の mode（{rec.get('mode')}）では headless で起こせない。セッションを開いて続ける", w)
    elif int(w.get("n", 0)) >= MAX_WAKES:
        report(ap, session, specs, f"止まったセッションを {MAX_WAKES} 回起こしたが進まない。セッションを開いて確かめる", w)
    elif isinstance(rec.get("cwd"), str) and Path(rec["cwd"]).is_dir():
        w["n"] = int(w.get("n", 0)) + 1
        try:
            wake(session, rec, w)
        except OSError as e:
            report(ap, session, specs, f"止まったセッションを起こす claude を起動できない（{type(e).__name__}）。PATH を確かめ、セッションを開いて続ける", w)
    else:
        report(ap, session, specs, "セッションの作業の場所が無い。セッションを開いて確かめる", w)
    save(wf, w)


def cmd_tick():
    import autopilot as ap
    import overnight

    names = {f.name.split(".")[0] for f in (home() / "sessions").glob("*.json")
             if f.name.endswith(".host.json") or f.name.count(".") == 1}  # 記録の無いセッションも報告のために見る
    for session in sorted(names):
        if host_file(session) is None:  # 受理集合の外の id は claude の引数に置かない
            print(f"{session!r}: session id の形が受理集合の外なので見回らない", file=sys.stderr)
            continue
        try:
            tick_one(ap, overnight, session)
        except Exception as e:  # 1 つのセッションの失敗で、ほかを見回らないことにしない
            print(f"{session}: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


def cmd_plist():
    log = home() / "watch" / "launchd.log"
    plist = {"Label": LABEL, "ProgramArguments": [sys.executable, str(HERE), "tick"], "StartInterval": 900,
             "RunAtLoad": True, "AbandonProcessGroup": True, "StandardOutPath": str(log), "StandardErrorPath": str(log),
             "EnvironmentVariables": {"PATH": os.environ.get("PATH", ""), "HOME": str(Path.home())}}
    sys.stdout.write(plistlib.dumps(plist).decode("utf-8"))
    return 0


def main(argv=None):
    cmd = (argv if argv is not None else sys.argv[1:]) or ["tick"]
    return {"tick": cmd_tick, "plist": cmd_plist}[cmd[0]]()


if __name__ == "__main__":
    sys.exit(main())
