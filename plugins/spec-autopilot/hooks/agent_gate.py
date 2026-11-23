#!/usr/bin/env python3
"""実装役（subagent_type の最後の `:` の後が autopilot-implementer で始まる）の起動を、dispatch が開いているときだけ通す
PreToolUse hook。prompt に書かれた spec のディレクトリ（state.json があるもの）のうち、phase が building・最後の dispatch を
閉じた handoff が無い・その dispatch の agent が起動する名前と同じ、の 3 つを満たすものが 1 つでもあれば何も出さない。
無ければ、prompt に spec が無い・state.json が読めない・途中の例外も含めて deny する。
想定するのは事故（dispatch の打ち忘れ）で、prompt に別の spec を書く・state.json を書き換える形は想定しない。
答えを出さずに終わった（import の失敗・終了コード 0 以外）ときの deny は、hooks.json の command が出す。"""
import json
import os
import re
import sys
from pathlib import Path

# CLI init が作る spec のディレクトリの名前（<日付>-<英小文字・数字・ハイフン>）を、prompt のパスの手がかりにする
ANCHOR = re.compile(r"docs/specs/\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*")


def short(name):
    return str(name or "").rsplit(":", 1)[-1]


def is_spec(path):
    """一致はファイルシステムの stat で決め、字を比べない（NFC・NFD を問わない照合と、実行だけの祖先の下でも引ける）。"""
    return os.path.isfile(os.path.join(path, "state.json"))


def anchored(line, start, stop, cwd, home):
    """line[start:stop] の手がかりで終わる spec のディレクトリ（無ければ None）。同じ行のその前の `/`・`~/` を始まりの候補にし、
    いちばん前から始まる存在するものを採る（絶対パスの中の `/` から届く別の綴りは数えない）。どれも無いときだけ、
    payload の cwd とその祖先の下の docs/specs/<名前> を候補にする（別の repo の絶対パスの途中を cwd の spec と取り違えない）。"""
    for i in range(start):
        if line[i] == "~" and line[i + 1:i + 2] == "/":
            cand = home + line[i + 1:stop]
        elif line[i] == "/" and not (i and line[i - 1] == "~"):
            cand = line[i:stop]
        else:
            continue
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
    候補の数は、手がかりの数 × その前の `/` の数。"""
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
    if s.get("phase") != "building":
        return f"{d} は building でない（{s.get('phase')}）"
    dispatches = s.get("dispatches") or []
    if not dispatches:
        return f"{d} に dispatch の記録が無い"
    n = len(dispatches) - 1
    if any(h.get("dispatch") == n for h in s.get("handoffs") or []):
        return f"{d} の最後の dispatch は handoff で閉じている"
    if short(dispatches[-1].get("agent")) != name:
        return f"{d} の最後の dispatch は {dispatches[-1].get('agent')} を指している（起動は {name}）"
    return None


def decide(payload):
    """(deny の理由 | None)。"""
    inp = payload.get("tool_input") or {}
    name = short(inp.get("subagent_type"))
    if not name.startswith("autopilot-implementer"):
        return None
    dirs = spec_dirs(str(inp.get("prompt") or ""), payload.get("cwd") or ".")
    if not dirs:
        return "prompt に spec のディレクトリ（state.json があるもの）が無いので、dispatch を確かめられない"
    reasons = []
    for d in dirs:
        why = problem(d, name)
        if why is None:
            return None
        reasons.append(why)
    return "; ".join(reasons)


def main():
    try:
        why = decide(json.loads(sys.stdin.buffer.read() or b"{}"))
    except Exception as e:
        why = f"判定の途中で例外が出た（{type(e).__name__}: {e}）"
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"実装役を起動できない: {why}。overnight.py dispatch <dir> --task T<n> を打ってから起動する"}},
            ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
