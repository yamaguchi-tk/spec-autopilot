#!/usr/bin/env python3
"""実装役（subagent_type の最後の `:` の後が autopilot-implementer で始まる）の起動を、dispatch が開いているときだけ通す
PreToolUse hook。prompt に書かれた spec のディレクトリ（state.json があるもの）のうち、phase が building（または discovery で「## 制約」の大きさが S の試作）・最後の dispatch を
閉じた handoff が無い・その dispatch の agent が起動する名前と同じ、の 3 つを満たすものが 1 つでもあれば何も出さない。
無ければ、prompt に spec が無い・state.json が読めない・途中の例外も含めて deny する。
評価役（autopilot-reviewer で始まる）の起動は、prompt に書かれた building の spec のうち、review を記録できる（overnight.review_gate が通る）ものが 1 つでもあれば、
通る spec の state.json の review_launches にだけ時刻を足して通す（書けなかったときは stderr に 1 行出して通す）。building の spec があるのにどれも通らなければ、
review_gate の文を spec ごとに出して deny する（review を記録できない状態では評価役を起動せず、overnight.py handoff を打ち直してから起動する）。
building の spec が 1 つも無い（読めない・building でない・prompt に spec が無い）ときは、何も残さずに通す。判定は review_gate 1 つを正本にし、条件を写さない。
実装役は、最後の評価役の起動より後に review の記録が無い spec も通さない（評価役の結果を記録してから起動し直す）。
想定するのは事故（dispatch の打ち忘れ・評価役の結果の記録の抜け）で、prompt に別の spec を書く・state.json を書き換える形は想定しない。
答えを出さずに終わった（import の失敗・終了コード 0 以外）ときの deny は、hooks.json の command が出す。"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import autopilot  # noqa: E402
import overnight  # noqa: E402

# CLI init が作る spec のディレクトリの名前（<日付>-<英小文字・数字・ハイフン>）を、prompt のパスの手がかりにする
ANCHOR = re.compile(r"docs/specs/\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*")


IMPL_DENY = "実装役を起動できない: "
IMPL_FIX = "。overnight.py dispatch <dir> --task T<n> を打ってから起動する"


def short(name):
    return str(name or "").rsplit(":", 1)[-1]


def is_spec(path):
    """一致はファイルシステムの stat で決め、字を比べない（NFC・NFD を問わない照合と、実行だけの祖先の下でも引ける）。"""
    return os.path.isfile(os.path.join(path, "state.json"))


# 相対パスの途中にある字（ここに続く位置は、相対パスの始まりの候補にしない）
PATH_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-/~")


def anchored(line, start, stop, cwd, home):
    """line[start:stop] の手がかりで終わる spec のディレクトリ（無ければ None）。候補を次の順に stat で確かめ、最初に存在するものを採る。
    1. 同じ行のその前の `/`・`~/` から始まる絶対パス（いちばん前から。絶対パスの中の `/` から届く別の綴りは数えない）
    2. その前の、行頭か、パスの字（英数字・`._-/~`）でない字の直後から始まる部分を、payload の cwd からの相対パスとしたもの
       （`sub/`・`.claude/worktrees/wt1/`・`../b/` のように docs/specs の前にディレクトリが付いた形。いちばん前から）
    3. payload の cwd とその祖先の下の docs/specs/<名前>
    1・2 の後に 3 を試すので、別の repo の絶対パスや、cwd の下の別の repo の相対パスを、cwd の spec と取り違えない。"""
    for i in range(start):
        if line[i] == "~" and line[i + 1:i + 2] == "/":
            cand = home + line[i + 1:stop]
        elif line[i] == "/" and not (i and line[i - 1] == "~"):
            cand = line[i:stop]
        else:
            continue
        if is_spec(cand):
            return cand
    for i in range(start):
        if line[i] not in "/~" and (i == 0 or line[i - 1] not in PATH_CHARS):
            cand = os.path.join(cwd, line[i:stop])
            if is_spec(cand):
                return cand
    rel, base = line[start:stop], cwd
    while True:
        cand = os.path.join(base, rel)
        if is_spec(cand):
            return cand
        parent = os.path.dirname(base)
        if parent == base:
            return None
        base = parent


def spec_dirs(prompt, cwd):
    """prompt の各行の docs/specs/<日付>-<slug> ごとに spec のディレクトリを引き、realpath で重ねて同じ spec を 1 度だけ数える。
    候補の数は、手がかりの数 × その前の字の数（`/` と、相対パスの始まりになる位置）。"""
    found, seen = [], set()
    cwd, home = os.path.abspath(cwd), os.path.expanduser("~")
    for line in prompt.splitlines():
        for m in ANCHOR.finditer(line):
            d = anchored(line, m.start(), m.end(), cwd, home)
            if d is None:
                continue
            key = os.path.realpath(d)
            if key not in seen:
                seen.add(key)
                found.append(Path(d))
    return found


def problem(d, name):
    """この spec で起動を通せない理由（通せるなら None）。"""
    try:
        s = json.loads((d / "state.json").read_text(encoding="utf-8"))
    except Exception as e:
        return f"{d} の state.json が読めない（{type(e).__name__}）"
    small, why = overnight.is_small(d) if s.get("phase") == "discovery" else (False, None)
    if not (s.get("phase") == "building" or small):
        return f"{d} は building でない（{s.get('phase')}。discovery は大きさ S だけ）" + (f"。{why}" if why else "")
    dispatches = s.get("dispatches") or []
    if not dispatches:
        return f"{d} に dispatch の記録が無い"
    n = len(dispatches) - 1
    if any(h.get("dispatch") == n for h in s.get("handoffs") or []):
        return f"{d} の最後の dispatch は handoff で閉じている"
    if short(dispatches[-1].get("agent")) != name:
        return f"{d} の最後の dispatch は {dispatches[-1].get('agent')} を指している（起動は {name}）"
    return overnight.ladder.unrecorded_review(d, s)


def review_gate_of(d):
    """building の spec なら review_gate の文（記録を受けるなら None）を (文,) で返す。building でない・読めない spec は None。"""
    try:
        s = autopilot.load_state(d)
        return (overnight.review_gate(d, s)[0],) if s.get("phase") == "building" else None
    except Exception:
        return None


def record_review_launch(d):
    """spec の review_launches に今の時刻を足す（書く直前に読み直す）。書けなかったときは、例外の型と spec のディレクトリを stderr に 1 行出して通す。"""
    try:
        s = autopilot.load_state(d)
        s.setdefault("review_launches", []).append(time.time())
        autopilot.save_state(d, s)
    except Exception as e:
        print(f"評価役の起動を記録できなかった（{type(e).__name__}）: {d}", file=sys.stderr)


def review_launch(dirs):
    """評価役の起動の deny の理由（通すなら None）。通る spec があればその spec にだけ記録して通す。"""
    gates = [(d, g[0]) for d in dirs if (g := review_gate_of(d))]
    if not gates or any(why is None for _, why in gates):
        for d, why in gates:
            if why is None:
                record_review_launch(d)
        return None
    return ("評価役を起動できない: " + "; ".join(f"{d}: {why}" for d, why in gates)
            + "。review を記録できない状態では評価役を起動しない。overnight.py handoff <dir> --task T<n> を打ち直してから起動する")


def decide(payload):
    """deny の理由（通すなら None）。"""
    inp = payload.get("tool_input") or {}
    name = short(inp.get("subagent_type"))
    is_reviewer = name.startswith("autopilot-reviewer")
    if not (is_reviewer or name.startswith("autopilot-implementer")):
        return None
    dirs = spec_dirs(str(inp.get("prompt") or ""), payload.get("cwd") or ".")
    if is_reviewer:
        return review_launch(dirs)
    if not dirs:
        return IMPL_DENY + "prompt に spec のディレクトリ（state.json があるもの）が無いので、dispatch を確かめられない" + IMPL_FIX
    reasons = []
    for d in dirs:
        why = problem(d, name)
        if why is None:
            return None
        reasons.append(why)
    return IMPL_DENY + "; ".join(reasons) + IMPL_FIX


def main():
    try:
        why = decide(json.loads(sys.stdin.buffer.read() or b"{}"))
    except Exception as e:
        why = IMPL_DENY + f"判定の途中で例外が出た（{type(e).__name__}: {e}）" + IMPL_FIX
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": why}},
            ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
