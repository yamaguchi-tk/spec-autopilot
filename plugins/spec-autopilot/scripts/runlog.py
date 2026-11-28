"""done・block の記録。SPEC_AUTOPILOT_HOME（無ければ ~/.claude/spec-autopilot）の runs.jsonl に、1 回につき 1 行を追記する。"""
import json
import os
import re
import time
from pathlib import Path

import stages

REWORK = re.compile(r"^- 手戻り元:[ \t]*(\S.*?)[ \t]*$", re.M)


def log_path():
    return Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot") / "runs.jsonl"


def minutes(seconds):
    return round(seconds / 60, 1)


def active_min(s, top_end):
    """承認から終わりまでの分の、巡ごとの和。top_end が None なら今の巡は足さない。足せる巡が無ければ None。"""
    total, found = 0.0, False
    for r in s.get("history") or []:
        if r.get("phase") == "wait" or r.get("approved_at") is None:
            continue
        end = r.get("done_at") or (r.get("blocked") or {}).get("at")
        if end is not None:
            total += end - r["approved_at"] - (r.get("paused_sec") or 0)
            found = True
    if top_end is not None and s.get("approved_at") is not None:
        total += top_end - s["approved_at"] - (s.get("paused_sec") or 0)
        found = True
    return minutes(total) if found else None


def record(d, s, kind, end, top_end="same"):
    """1 行を追記する。書けなければ NOTE を出す。top_end は今の巡の終わり（既定は end、None で今の巡を足さない）。"""
    d = Path(d)
    try:
        text = stages.COMMENT_BLOCK.sub("", (d / "spec.md").read_text(encoding="utf-8"))
        constraints = stages.section(text, "制約") or ""
        size = stages.stated_size(constraints)[0]
        rework = REWORK.search(constraints)
        history = s.get("history") or []
        blocks = [r["blocked"] for r in history if r.get("blocked")]
        if kind == "block" and s.get("blocked"):
            blocks.append(s["blocked"])
        prs = []
        for m in [m for r in history for m in r.get("merges") or []] + list(s.get("merges") or []):
            if m.get("pr") not in prs:
                prs.append(m.get("pr"))
        row = {"kind": kind, "at": time.time(), "spec": d.resolve().name, "repo": str(stages.repo_root(d).resolve()),
               "active_min": active_min(s, end if top_end == "same" else top_end),
               "total_min": minutes(end - s["created_at"]), "size": size,
               "blocks": [{"req": b.get("req"), "reason": b.get("reason")} for b in blocks],
               "rework_of": rework.group(1) if rework else None, "prs": prs, "light": bool(s.get("light"))}
        f = log_path()
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:  # 記録が書けなくても done・block は通す
        print(f"NOTE: runs.jsonl に書けなかった（{type(e).__name__}: {e}）。この回の記録は残らない")
