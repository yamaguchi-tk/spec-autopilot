#!/usr/bin/env python3
"""自走中（承認済みで未完了の spec がある）に、完了の検査が通るまで turn を終えさせない Stop hook。

- 止めるのは: phase=building の spec で `autopilot.py check` が通らないとき。spec ごとに判定する
- 放すのは次だけ: このセッションの記録に building の spec が無い・check が通る・予算の 2 倍（確認待ちを除く）・background の agent の待ち中に期限 timer が生きているとき（下）・
  最初の block の後の続行の間の、phase の読めない spec と hook 自身の例外・payload が読めないとき（下）。ほかは止める
- 見る spec は、自走を引き受けたとき（approve・resume・adopt）にこのセッションの記録に書いた絶対パスだけ。
  cwd の repo の spec は見ない（fork や同じ repo の別のセッションを止めないため）。記録の無いセッションは止めない
- セッションの記録が壊れている・記録した spec が消えたときは、読めない spec として扱う
- phase が building と分かった spec は、成果物が読めなくても止める。phase が許可リストに無い値なら読めない spec として扱う
- 連続 block の上限は Claude Code に任せる（自前では数えない）
- 自走の異常の件数（autopilot.anomalies）は知らせるだけで、止める・放すには使わない（with_notice）
- 止める理由があっても、このセッションが background で起動した agent を待っていて、起こし直しの期限 timer
  （background の単独の `sleep <秒>`、60〜900 秒、起動応答のあるもの）が生きていれば放す。timer が生きているとみなすのは、
  時計の上で切れておらず、次のどちらかのときだけ。(1) この Claude Code のプロセス（hook の祖先のうち shell でない最初のもの）の
  子孫に、同じ秒数の `sleep` が、張った時刻の前後 3 秒に起きて今も動いている（ps で確かめる）。(2) その timer がこの turn の
  最後の tool で、起動応答の後に通知・人の発言が届いていない（起動の直後なので必ず動いている。ps が使えないときの道）。
  timer の死んだ証拠（通知・開き直しの記録）は読まない。後の tool の入力に timer の id が出たら、止められたかもしれないので数えない。
  待ち中とみなすのは、host の meta.json があり、起動・再開より後の finished が無く、agent の transcript が
  15 分以内に書かれているときだけ。生きている timer が無ければ、timer を 1 本張ってから終えるよう求める短い
  理由で止める。読めないときは止める。background の Bash の待ちは数えない
- state.json が読めず phase が分からない spec は止める側に倒す。ただし最初の block の後の続行の間
  （payload の stop_hook_active が true）は、その spec だけを放す（人を閉じ込めないための弁）
- 確認待ち（wait）の時間は予算に数えない
- 終われるのは: done・blocked・wait（安全規則の確認待ち）・壁打ち中（discovery）・spec が無い
- まとめて承認した spec（queued）か、脇に置いたレビュー待ち（wait の kind=review）が残り、自走中の spec が無い（予算の 2 倍を過ぎたものを除く）
  ときは、lineup.py next（予算の 2 倍を過ぎた spec があれば、その block の後に）を求めて止める（夜の間に行列を止めない）
- 予算の 2 倍を過ぎたら止めない（収束しないループで費用を使い続けないため）。そのときは block を促す
- payload が読めないときは止めない（stop_hook_active も読めないため）。autopilot.py が import できないときは、判定の途中の例外と同じく扱う
- 1 回の判定には時間の予算（BUDGET_SEC。host の timeout 30 秒より短く）がある。予算を過ぎたら、まだ判定していない spec は
  読めない spec として扱い（最初の停止では止め、続行中は放す）、transcript の走査（待ちの判定）は待ち中なしとして扱い、
  異常の知らせは数え終えた spec の分だけを出す
- 判定の途中の SystemExit・KeyboardInterrupt なども、例外と同じく最初の停止では止め、続行中だけ放す。
  判定を出さずに終わったとき（シグナル・終了コード 0 以外）は、hooks.json が起動する wrapper（stop.sh）が同じように答える
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

BUDGET_SEC = 20  # host の timeout（hooks.json の 30 秒）から、起動と出力の分を残す
WATCHDOG_SEC = 25  # 協調の予算が効かない処理（正規表現の C の中など）でも、OS が殺して stop.sh の止める側に落とす
RELEASED = ("discovery", "done", "blocked", "wait", "queued")  # 放す phase はこれだけ。ほかの値は読めないものとして扱う
CONTINUE = ("自走中の spec が完了の検査を通っていない。人に聞かずに続ける。"
            "spec の `- 範囲:` が含む段の操作（範囲がマージ以上ならその PR のマージ、範囲に書いたデプロイの起動、QA の書き込み先への書き込み）は確かめずに進める。"
            "ユーザーの CLAUDE.md の安全規則が 1 操作ごとの確認を求める操作と範囲の外の操作は、実行せず overnight.py park で積む。"
            "1 つの要件だけを満たせないときも park で積んで残りを進める。"
            "積んでいない要件が 1 つも進められないときだけ autopilot.py block で記録して終える。")


def judge(autopilot, d, record=True):
    """(止める理由, 知らせ) を返す。どちらも無ければ (None, None)。読めなければ例外を投げる。
    record が偽なら state.json に書かない（見回り役 watch.py がセッションの外から判定するとき）。"""
    s = autopilot.load_state(d)
    if s.get("phase") in RELEASED:
        return None, None
    if s.get("phase") != "building":
        raise ValueError(f"phase={s.get('phase')!r}")
    try:  # phase が building と分かった後は、読めないものも止める理由にする（弁に回さない）
        return judge_building(autopilot, d, s, record)
    except Exception as e:
        return f"{d.name}: 成果物か state.json の値が読めない（{type(e).__name__}）。直して続ける", None


def judge_building(autopilot, d, s, record=True):
    import overnight

    elapsed, budget, label = overnight.budget_view(d, s)
    if elapsed > 2 * budget:
        bad = overnight.production_errors(d, s)
        if bad:  # 壊れた・確かめていない本番を残して放さない（block は phase を変えるので閉じ込めない）
            return (f"{d.name}: {label}の予算の 2 倍を過ぎたが、{bad[0]}。"
                    "戻せないなら block --no-rollback で理由を書いて人に示す"), None
        return None, f"{d.name}: {label}の予算 {budget:.0f} 分の 2 倍を過ぎた。満たせないなら block を記録して人に示す"
    try:  # 最後の活動の時刻を残す（中断の後の再開で、止まっていた時間を予算から外す）。書けなくても判定は続ける
        if record:
            autopilot.save_state(d, s)
    except OSError:
        pass
    errors, _ = autopilot.check(d)
    if errors and awaiting(overnight, d):
        return None, None  # 機械の待ちのプロセスが生きている。終わりの通知で起きた後の停止で check を当て直す
    if errors:
        return f"{d.name}（{label} {elapsed:.0f} 分 / 予算 {budget:.0f} 分）:\n- " + "\n- ".join(errors), None
    return None, None


def awaiting(overnight, d, now=None, processes=None):
    """spec の機械の待ち（overnight.py await）が生きているか。放すのは次のすべてを満たすときだけで、読めなければ False:
    記録（await.json）が読める・今が記録の期限より前・pid が host の子孫・argv に overnight.py と await と spec の絶対パス・
    ps の経過時間が記録の開始時刻と前後 WINDOW_SEC で合う（pid の再利用と、別のセッションの await を数えない）。"""
    try:
        rec = overnight.await_record(d)
        now = time.time() if now is None else now
        if rec is None or not (rec["started_at"] - WINDOW_SEC <= now < rec["deadline"]):
            return False
        procs = (processes or _processes)(timeout=3)
        host = _host(procs) if procs else None
        if host is None or rec["pid"] not in procs or not _under(procs, rec["pid"], host):
            return False
        _, elapsed, argv = procs[rec["pid"]]
        joined = " ".join(argv)
        return (any(Path(x).name == "overnight.py" for x in argv) and "await" in argv and (str(d) in joined or str(d.resolve()) in joined)
                and abs(now - elapsed - rec["started_at"]) <= WINDOW_SEC)
    except Exception:
        return False


def find_root(start):
    """cwd から親へたどり、.git のある最初の階層（repo の root）を返す（git を起動しない）。無ければ None。
    承認には git dir の発言の記録が要るので、自走中の spec は git の repo の中にしか無い。
    cwd が実在しないディレクトリなら例外にする（main が最初の停止で止める）。"""
    start = start.resolve()
    if not start.is_dir():
        raise NotADirectoryError(str(start))
    for p in (start, *start.parents):
        if (p / ".git").exists():
            return p
    return None


def recorded(autopilot, payload, unreadable):
    """このセッションが自走を引き受けた spec（Stop hook が止める理由にするのはこれだけ）。"""
    try:
        return _unique(autopilot.recorded_specs(payload.get("session_id")), unreadable)
    except Exception as e:
        unreadable.append(f"このセッションの spec の記録が読めない（{type(e).__name__}）")
        return []


def candidates(autopilot, payload, unreadable):
    """記録したパスと cwd の repo の spec を、重ねずに並べる（SessionStart が状態を知らせるため）。"""
    dirs = recorded(autopilot, payload, unreadable)
    try:  # 入力の源ごとに例外を受け、読めた側の spec は残す
        root = find_root(Path(payload.get("cwd") or "."))
        if root is not None:
            dirs += autopilot.spec_dirs(root)
    except Exception as e:
        unreadable.append(f"cwd の repo を読めない（{type(e).__name__}）")
    return _unique(dirs, unreadable)


def _unique(dirs, unreadable):
    seen, out = set(), []
    for d in dirs:
        try:
            key = d.resolve()
        except Exception as e:
            unreadable.append(f"記録した spec の場所が読めない（{type(e).__name__}）")
            continue
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


# background の agent の待ち（Desktop の Agent には前景が無い）。放すのは、待ち中の agent があり、起こし直しの期限
# timer（background の単独の `sleep <秒>`、15 分以下）が生きているときだけ。timer の生死は、sleep の process を ps で
# 確かめて決める。死んだ証拠（通知など）を探して外す決め方はしない（拾いそこねた形が放す側に残るため）
ALIVE_SEC = 15 * 60  # subagent の transcript がこの間に書かれていなければ、終わりを残さずに死んだ agent とみなす
TIMER_MAX_SEC = 15 * 60
TIMER_MIN_SEC = 60  # 停止より前に切れて、その終わりの通知が turn の中で使われる短い sleep を timer に数えない
TIMER_HINT = ("background の agent の終わりを待っている。Bash で `sleep 900` を run_in_background: true で 1 本張り、"
              "ほかの tool を呼ばずに turn を終える。待っている agent が残る間は、張った timer を止めない（時計の上で生きている timer があれば止めない）。"
              "turn を終える時点で待っている agent が無くなったら、その timer を TaskStop で止める")
_AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")
_SLEEP = re.compile(r"[ \t]*sleep[ \t]+([0-9]+)[ \t]*")
SHELLS = ("sh", "bash", "zsh", "dash")  # host を探すとき、hook と sleep の間に挟まる shell は飛ばす
WINDOW_SEC = 3  # sleep が起きた時刻と、tool_use・起動応答の時刻の差の許し（ps の経過時間は秒で切れる）


def _epoch(ts):
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return t.timestamp() if t.tzinfo is not None else None
    except Exception:
        return None


def scan(path, deadline=None):
    """transcript から (起動・再開した agent の id → 時刻, 期限 timer の [(id, 張った時刻, 起動応答の時刻, 秒)], この turn の
    最後の tool の timer の id か None)。timer は起動応答（backgroundTaskId）があり、後の tool の入力にその id が出ていないものだけ。
    deadline を過ぎたら autopilot.Overdue を投げる。"""
    from autopilot import transcript_lines

    agents, pending, timers, last, fresh = {}, {}, {}, None, None
    for line in transcript_lines(path, deadline):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        at = _epoch(r.get("timestamp"))
        m = r.get("message")
        content = m.get("content") if isinstance(m, dict) else None
        blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
        if r.get("type") == "assistant":
            for b in blocks:
                if b.get("type") != "tool_use":
                    continue
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                named = json.dumps(inp, ensure_ascii=False)
                for task in [t for t in timers if t in named]:  # 止めたかもしれない timer は数えない
                    del timers[task]
                last, fresh = b.get("id"), None
                s = _SLEEP.fullmatch(inp.get("command")) if isinstance(inp.get("command"), str) else None
                if (b.get("name") == "Bash" and inp.get("run_in_background") is True and s and isinstance(b.get("id"), str)
                        and at is not None and TIMER_MIN_SEC <= int(s.group(1)) <= TIMER_MAX_SEC):
                    pending[b["id"]] = (at, int(s.group(1)))
            continue
        res = r.get("toolUseResult")
        if r.get("type") == "user" and isinstance(res, dict):
            agent = res.get("agentId") if res.get("status") == "async_launched" else (
                res.get("resumedAgentId") if res.get("success") is True else None)
            if isinstance(agent, str) and _AGENT_ID.fullmatch(agent) and at is not None:
                agents[agent] = at
            task = res.get("backgroundTaskId")
            acks = [b.get("tool_use_id") for b in blocks if isinstance(b.get("tool_use_id"), str)]
            ack = next((t for t in acks if t in pending), None)
            if isinstance(task, str) and task and ack is not None:
                used, sec = pending.pop(ack)
                timers[task] = (task, used, used if at is None else at, sec)
                if ack == last:
                    fresh = task
                continue
        if fresh is not None and (r.get("type") in ("user", "queue-operation") or (
                r.get("type") == "attachment" and isinstance(r.get("attachment"), dict)
                and r["attachment"].get("type") == "queued_command")):
            fresh = None  # 起動応答の後に main へ入力が届いた（通知・人の発言）。この turn の timer ではない
    return agents, list(timers.values()), fresh if fresh in timers else None


def _elapsed(text):
    """ps の etime（[[dd-]hh:]mm:ss）を秒にする。"""
    days, _, rest = text.strip().rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    sec = 0
    for x in parts:
        sec = sec * 60 + x
    return sec + int(days or 0) * 86400


def _processes(timeout=5):
    """pid → (ppid, 起きてからの秒, argv) を ps で読む。読めなければ None。"""
    try:
        out = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,ppid=,etime=,command="], capture_output=True, text=True,
                             timeout=timeout, check=True).stdout
        procs = {}
        for line in out.splitlines():
            pid, ppid, etime, *cmd = line.split(None, 3)
            procs[int(pid)] = (int(ppid), _elapsed(etime), cmd[0].split() if cmd else [])
        return procs
    except Exception:
        return None


def _host(procs):
    """hook の祖先のうち、shell でない最初のもの（Claude Code のプロセス）。見つからなければ None。"""
    pid = os.getppid()
    for _ in range(50):
        if pid not in procs or pid <= 1:
            return None
        argv = procs[pid][2]
        if not argv or Path(argv[0]).name.lstrip("-") not in SHELLS:
            return pid
        pid = procs[pid][0]
    return None


def _under(procs, pid, host):
    for _ in range(50):
        if pid == host:
            return True
        if pid not in procs or pid <= 1:
            return False
        pid = procs[pid][0]
    return False


def _sleeping(procs, host, timer, now):
    """host の子孫に、timer と同じ秒数の sleep が、張った時刻の前後に起きて動いている。"""
    _, used, acked, sec = timer
    for pid, (ppid, elapsed, argv) in procs.items():
        if (len(argv) == 2 and Path(argv[0]).name == "sleep" and argv[1] == str(sec)
                and used - WINDOW_SEC <= now - elapsed <= acked + WINDOW_SEC and _under(procs, ppid, host)):
            return True
    return False


def _running(subagents, agent, launched_at, now):
    """host の meta.json があり、起動・再開より後の finished が無く、transcript が新しい。読めなければ False。"""
    try:
        meta = subagents / f"agent-{agent}.meta.json"
        d = json.loads(meta.read_text(encoding="utf-8"))
        if d.get("finished") not in (None, False) and meta.stat().st_mtime >= launched_at:
            return False
        return now - (subagents / f"agent-{agent}.jsonl").stat().st_mtime < ALIVE_SEC
    except Exception:
        return False


def wait_state(payload, now=None, processes=_processes, deadline=None):
    """"release"（待ち中で、生きている timer がある）・"timer"（待ち中で timer が無い）・None（待ち中なし。読めないときと、
    deadline を過ぎたときも）。ps は deadline までの残りの時間で読み、残りが無ければ読まない（timer を求める側に倒す）。"""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    try:
        now = time.time() if now is None else now
        agents, timers, fresh = scan(path, deadline)
        subagents = Path(path).parent / Path(path).stem / "subagents"
        if not any(_running(subagents, a, at, now) for a, at in agents.items()):
            return None
        timers = [t for t in timers if t[1] <= now < t[1] + t[3]]  # 時計の上で切れた timer は数えない
        if any(t[0] == fresh for t in timers):
            return "release"
        left = 5 if deadline is None else min(5, deadline - time.monotonic())
        procs = processes(timeout=left) if timers and left > 0 else None
        host = _host(procs) if procs else None
        if host is not None and any(_sleeping(procs, host, t, now) for t in timers):
            return "release"
        return "timer"
    except Exception:
        return None


def overdue(deadline):
    return deadline is not None and time.monotonic() > deadline


def decide(autopilot, payload, deadline=None):
    retry = bool(payload.get("stop_hook_active"))
    reasons, unreadable, notices = [], [], []
    for d in recorded(autopilot, payload, unreadable):
        if overdue(deadline):  # 判定し終えないまま host の timeout で放されないよう、残りは読めない spec に回す
            unreadable.append(f"{d.name}: 時間の上限（{BUDGET_SEC} 秒）までに判定できなかった。続けて、次の停止で判定し直す")
            continue
        try:
            reason, notice = judge(autopilot, d)
        except Exception as e:  # 1 件の破損でほかの spec を放さない
            unreadable.append(f"{d.name}: 判定できない（{type(e).__name__}）。state.json と成果物を直す")
            continue
        if reason:
            reasons.append(reason)
        if notice:
            notices.append(notice)
    if not reasons and not unreadable:
        try:
            nxt = lineup_demand(autopilot, payload)
        except Exception as e:
            nxt = None
            unreadable.append(f"まとめて承認した spec の行列を読めない（{type(e).__name__}）。lineup.py next を回して確かめる")
        if nxt:
            reasons.append(nxt)
    if unreadable and retry:
        notices.extend(unreadable)
        unreadable = []
    state = wait_state(payload, deadline=deadline) if reasons or unreadable else None
    if state == "release":
        return None  # 起き直した後の停止で check を当て直す
    if state == "timer":  # agent の終わりを待つしかないので、残りの検査は並べず timer だけを求める
        return {"decision": "block", "reason": "\n\n".join([TIMER_HINT] + unreadable)}
    if reasons or unreadable:
        return {"decision": "block", "reason": CONTINUE + "\n\n" + "\n\n".join(reasons + unreadable)}
    if notices:
        return {"systemMessage": "\n".join(notices)}
    return None


def lineup_demand(autopilot, payload):
    """まとめて承認した spec の行列を進める要求の文か None。"""
    import lineup
    import overnight

    rows = [(d, autopilot.load_state(d)) for d in recorded(autopilot, payload, [])]
    over = {d for d, s in rows if s.get("phase") == "building" and (lambda v: v[0] > 2 * v[1])(overnight.budget_view(d, s))}
    return lineup.demand(rows, over)


def anomaly_notice(autopilot, payload, deadline=None):
    """自走中の spec ごとに、承認からの異常の件数を transcript で数え、前の停止より増えた型を知らせる文を返す。
    件数は state.json の anomalies に残す（done の報告が読む）。止める・放すの判定には使わない。
    deadline を過ぎたら、数え終えた spec の分だけを返す。"""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    lines = []
    for d in recorded(autopilot, payload, []):
        s = autopilot.load_state(d)
        if s.get("phase") != "building":
            continue
        try:
            counts = autopilot.anomalies(path, since=float(s["approved_at"]), deadline=deadline) or {}
        except autopilot.Overdue:
            break
        before = s.get("anomalies") or {}
        grown = {k: v for k, v in counts.items() if v > before.get(k, 0)}
        if grown:
            s["anomalies"] = {**before, **counts}
            autopilot.save_state(d, s)
            lines.append(f"{d.name}: 自走の異常（手順の約束から外れた動き）: {autopilot.anomaly_line(grown)}")
    return "\n".join(lines) or None


def with_notice(autopilot, payload, out, deadline=None):
    """判定の結果に異常の知らせを足す。数えられないときは判定の結果をそのまま返す。"""
    try:
        msg = anomaly_notice(autopilot, payload, deadline)
    except Exception:
        return out
    if not msg:
        return out
    out = dict(out or {})
    out["systemMessage"] = "\n".join(x for x in (out.get("systemMessage"), msg) if x)
    return out


def main():
    deadline = time.monotonic() + BUDGET_SEC
    try:
        payload = json.loads(sys.stdin.buffer.read() or b"{}")  # bytes で読む（stdio の文字コードに依らない）
        retry = bool(payload.get("stop_hook_active"))
    except Exception as e:  # payload が読めないときは stop_hook_active も読めないので、止めない
        out = {"systemMessage": f"spec-autopilot の Stop hook を読めなかったので止めない: {type(e).__name__}"}
    else:
        try:
            import autopilot

            out = with_notice(autopilot, payload, decide(autopilot, payload, deadline), deadline)
            try:  # 見回り役が権限の mode を読む。ps は呼ばず、予算を過ぎていれば書かない。書けなくても判定は変えない
                __import__("watch").note_stop(payload, deadline)
            except Exception:
                pass
        except BaseException as e:  # import と判定の途中の例外（SystemExit なども）は、最初の停止では止め、続行中だけ放す
            msg = f"spec-autopilot の Stop hook が判定できない（{type(e).__name__}）"
            out = {"systemMessage": msg + "ので放す"} if retry else {"decision": "block", "reason": msg + "。docs/specs の state.json と成果物を確かめて続ける"}
    if out:
        print(json.dumps(out))  # ASCII だけにする（stdout の文字コードで落ちて放さないため）
    return 0


if __name__ == "__main__":
    import signal

    signal.alarm(WATCHDOG_SEC)  # handler は入れない（既定の動作で process が終わる。handler は C の中では動かない）
    sys.exit(main())
