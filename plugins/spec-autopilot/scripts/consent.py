#!/usr/bin/env python3
"""承認の門（人の発言・相談役の記録）が「いつより後」を数えるかの起点を、承認の中身のハッシュで決める。

- 承認の中身のハッシュは、spec.md の全体（作り方の節を含める）から、先頭の `- ADR:` 行の連番の桁だけを外して計算する。
  連番は並行の branch との番号の取り合いで改番されるので外す。要件・作り方の文は 1 文字でも変えれば別のハッシュになる
- `autopilot.py lint` の CLI が通ったときだけ、{ハッシュ, そのハッシュを初めて見た時刻} を state.json の `consent` に残す
  （同じハッシュでは時刻を書き換えない）。approve の中の lint の検査は記録しない
- 起点は、今のハッシュの記録があればその時刻（spec.md の最後の変更の時刻より前のときだけ。連番だけの直しで spec.md が
  新しくなっても、人が見た中身の記録まで戻る）。記録が無い・読めないときは spec.md の最後の変更の時刻
- 想定するのは事故（中身の違う spec で承認を通すこと）。state.json の偽造は守らない
"""
import fcntl
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

ADR_LINE = re.compile(r"^- ADR:\s*(\S+)\s*$", re.M)
OWN_ADR = "\0ADR\0"  # 本文に素では書けない置き換え記号
ADR_NUMBER = re.compile(r"(?!\d{4}-\d{2}-\d{2}-)(\d+)-")  # 連番の ADR のファイル名の番号。日付の名前は番号と読まない
GATED = ("discovery", "blocked", "done")  # approve が受ける phase。ほかの phase の state.json は書かない


def numberless(head):
    """spec の先頭（最初の `## ` より前）の `- ADR:` 行から、連番の桁を外す（ディレクトリと slug は残す）。"""
    def one(m):
        folder, name = os.path.split(m.group(1))
        number = ADR_NUMBER.match(name)
        return m.group(0).replace(m.group(1), os.path.join(folder, OWN_ADR + name[number.end(1):])) if number else m.group(0)

    return ADR_LINE.sub(one, head)


def content_sha(text):
    """承認の中身のハッシュ。作り方の節を含め、先頭の `- ADR:` 行の連番の桁だけを外す。"""
    head, sep, rest = text.partition("\n## ")
    return hashlib.sha256((numberless(head) + sep + rest).encode("utf-8")).hexdigest()


def valid(rec):
    """記録の形の厳密な検査。{sha256: 64 桁の 16 進, at: 有限の数}。"""
    return (isinstance(rec, dict) and set(rec) == {"sha256", "at"} and isinstance(rec["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", rec["sha256"]) is not None
            and isinstance(rec["at"], (int, float)) and not isinstance(rec["at"], bool) and math.isfinite(rec["at"]))


def origin(d, s):
    """承認の門の起点（秒）。今の中身の記録があればその時刻、無ければ spec.md の最後の変更の時刻。"""
    spec = d / "spec.md"
    mtime = spec.stat().st_mtime
    rec = s.get("consent")
    if valid(rec) and rec["sha256"] == content_sha(spec.read_text(encoding="utf-8")):
        return min(rec["at"], mtime)
    return mtime


def record(d):
    """lint が通った spec の中身を残す。lint 同士が同時に書いても互いの記録を落とさないよう、spec のディレクトリの fd に
    flock を取り（ロック用のファイルは作らない）、その中で state.json を読み直し、`consent` だけを当てる。
    守るのは lint 同士の書き込みだけで、ほかのコマンドの state.json の書き込みとは排他にならない。
    返すのは利用者に知らせる NOTE の文。"""
    notes = []
    f = d / "state.json"
    if not f.is_file():
        return notes
    digest = content_sha((d / "spec.md").read_text(encoding="utf-8"))
    fd = os.open(d, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            phase = s.get("phase")
        except (OSError, ValueError, AttributeError) as e:
            return [f"state.json が読めない（{type(e).__name__}）ので、承認の中身の記録は残さない"]
        if phase not in GATED:
            return notes
        cur = s.get("consent")
        if valid(cur) and cur["sha256"] == digest:
            return notes
        if "consent" in s and not valid(cur):
            kept = d / f"state.json.consent-broken-{time.time_ns()}"
            kept.write_text(json.dumps(cur, ensure_ascii=False) + "\n", encoding="utf-8")
            notes.append(f"state.json の consent の形が違う。元の中身は {kept.name} に残し、今の中身で記録し直す")
        s["consent"] = {"sha256": digest, "at": time.time()}
        tmp = d / f".state.json.{os.getpid()}"
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, f)
    finally:
        os.close(fd)
    return notes
