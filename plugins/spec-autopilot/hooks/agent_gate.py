#!/usr/bin/env python3
"""実装役（subagent_type の最後の `:` の後が autopilot-implementer で始まる）の起動を、dispatch が開いているときだけ通す
PreToolUse hook。prompt に書かれた spec のディレクトリ（state.json があるもの）のうち、phase が building・最後の dispatch を
閉じた handoff が無い・その dispatch の agent が起動する名前と同じ、の 3 つを満たすものが 1 つでもあれば何も出さない。
無ければ、prompt に spec が無い・state.json が読めない・途中の例外も含めて deny する。
想定するのは事故（dispatch の打ち忘れ）で、prompt に別の spec を書く・state.json を書き換える形は想定しない。
答えを出さずに終わった（import の失敗・終了コード 0 以外）ときの deny は、hooks.json の command が出す。"""
import bisect
import json
import os
import sys
from pathlib import Path

NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")


def short(name):
    return str(name or "").rsplit(":", 1)[-1]


class Fs:
    """ディレクトリの一覧と state.json の有無を、1 回の判定のあいだ覚えておく。"""

    def __init__(self):
        self.names, self.specs = {}, {}

    def list(self, base):
        if base not in self.names:
            try:
                found = os.listdir(base)
            except OSError:
                found = []
            self.names[base] = sorted(set(found) | {".", ".."})
        return self.names[base]

    def has_prefix(self, base, part):
        names = self.list(base)
        i = bisect.bisect_left(names, part)
        return i < len(names) and names[i].startswith(part)

    def has_name(self, base, part):
        names = self.list(base)
        i = bisect.bisect_left(names, part)
        return i < len(names) and names[i] == part

    def is_spec(self, base, part):
        key = (base, part)
        if key not in self.specs:
            self.specs[key] = os.path.isfile(os.path.join(base, part, "state.json"))
        return self.specs[key]


def reach(line, base, k, fs, memo):
    """line[k:] を base の下のパスの続きとして 1 字ずつ伸ばし、state.json を持つディレクトリになった最長の終わりの位置（無ければ -1）。
    伸ばすのは、base の下に今の部分で始まる名前があるあいだだけ。(base, k) ごとに 1 回だけ求める。"""
    n, chain = len(line), []
    while (base, k) not in memo:
        best, nxt, j = -1, None, k
        while True:
            part = line[k:j]
            if part and fs.has_name(base, part) and fs.is_spec(base, part):
                best = j
            if j >= n:
                break
            if line[j] == "/":
                if not part:
                    nxt = (base, j + 1)
                elif fs.has_name(base, part) and os.path.isdir(os.path.join(base, part)):
                    nxt = (os.path.normpath(os.path.join(base, part)), j + 1)
                break
            if not fs.has_prefix(base, part + line[j]):
                break
            j += 1
        chain.append(((base, k), best))
        if nxt is None:
            memo[(base, k)] = best
            chain.pop()
            tail = best
            break
        base, k = nxt
    else:
        tail = memo[(base, k)]
    for state, best in reversed(chain):
        tail = max(best, tail)
        memo[state] = tail
    return tail


def spec_dirs(prompt, cwd):
    """prompt の各行の、どの位置からでも（相対パスは、直前が「/」か英数字・「_.-」でない位置から）、state.json を持つディレクトリになる最長の部分を探す（空白・日本語を含むパスも拾う）。
    終わりは区切りの字で限らず、始まりから存在するパスの接頭辞であるあいだだけ伸ばす（行の長さに対して線形）。"""
    found, fs = [], Fs()
    cwd, home = os.path.abspath(cwd), os.path.expanduser("~")
    for line in prompt.splitlines():
        memo = {}
        for i, c in enumerate(line):
            if c == "/":
                if i and line[i - 1] == "/":
                    continue
                end = reach(line, "/", i + 1, fs, memo)
            elif c == "~" and line[i + 1:i + 2] == "/":
                end = reach(line, home, i + 2, fs, memo)
            elif i and (line[i - 1] == "/" or line[i - 1] in NAME_CHARS):
                continue  # 別のパスや語の途中から始まる相対パスは読まない（絶対パスの中の docs/specs/x を cwd の下の別の spec と取り違えない）
            else:
                end = reach(line, cwd, i, fs, memo)
            if end > 0:
                p = Path(line[i:end]).expanduser()
                p = p if p.is_absolute() else Path(cwd) / p
                if p not in found:
                    found.append(p)
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
