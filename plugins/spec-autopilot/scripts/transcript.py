"""transcript を読んで、自走の異常を型ごとに数える（autopilot.py anomalies・done の報告・Stop hook の知らせ・human_said_at が使う）。"""
import datetime
import json
import re
import time

# 自走の異常: 手順（commands/autopilot.md）の約束から外れた動きを、main の transcript から型ごとに数える。
# 止める・放すには使わず、Stop hook の知らせ・done の報告・過去の transcript の集計にだけ使う
ANOMALY_KINDS = ("空の turn の block", "裏で走った agent", "承認後に人へ問い", "待ちの poll")
EMPTY_BLOCKS = 3  # tool を呼ばない turn が続けてこの回数止められたら 1 件（待ちのたびに止め続けた ECS の型）
POLL_SEC = 30
APPROVED_OUT = re.compile(r"approved: 予算 \d+ 分。ここから自走する")
DONE_OUT = re.compile(r"done: 承認から [\d.]+ 分")
WAIT_OUT = re.compile(r"^wait: 確認を人に 1 通で示す")
RESUME_OUT = re.compile(r"^resume: 自走に戻る")
_LOOP = re.compile(r"\b(until|while)\b")
_LOOP_SLEEP = re.compile(r"\bsleep\s+\d")  # _LOOP の後ろから探す（間を正規表現でつなぐと command の長さの 2 乗の時間がかかる）
_SLEEP_SEC = re.compile(r"(?:^|[;&|(]\s*|\bdo\s+)sleep\s+(\d+)")
_LONE_SLEEP = re.compile(r"[ \t]*sleep[ \t]+[0-9]+[ \t]*")
_NOT_HUMAN = ("<", "Stop hook feedback", "This session is being continued", "[Request interrupted")


def _iso_epoch(ts):
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _results(content):
    """tool_result の (tool_use_id, 本文) の並び。"""
    out = []
    for b in content if isinstance(content, list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            c = b.get("content")
            out.append((b.get("tool_use_id"), c if isinstance(c, str) else _text(c)))
    return out


class Overdue(Exception):
    """Stop hook の 1 回の予算（時刻）を過ぎた。"""


def transcript_lines(path, deadline=None):
    """transcript を 1 行ずつ返す。b"\\n" だけで割る（本文の U+2028 や \\r で割らない）。
    deadline（time.monotonic() の時刻）を過ぎたら Overdue を投げる。"""
    with open(path, "rb") as f:
        for raw in f:
            if deadline is not None and time.monotonic() > deadline:
                raise Overdue()
            yield raw.rstrip(b"\n").decode("utf-8", errors="replace")


def _polls(inp):
    cmd = inp.get("command") if isinstance(inp.get("command"), str) else ""
    if inp.get("run_in_background") is True and _LONE_SLEEP.fullmatch(cmd):  # 起こし直しの timer（手順の例外）は数えない
        return False
    loop = _LOOP.search(cmd)
    return bool(loop and _LOOP_SLEEP.search(cmd, loop.end())) or any(int(m.group(1)) >= POLL_SEC for m in _SLEEP_SEC.finditer(cmd))


def anomalies(path, since=None, deadline=None):
    """型ごとの件数を返す。since（epoch）があればその時刻から、無ければ transcript の中の approve の出力から、
    done の出力までを数える。approve が見つからなければ None。subagent の行は数えない。読めなければ例外を投げる。
    deadline を過ぎたら Overdue を投げる（途中までの件数は返さない）。"""
    counts = dict.fromkeys(ANOMALY_KINDS, 0)
    on, own, agents = False, {}, {}
    tools = streak = 0
    waiting = False  # wait（1 操作ごとの確認）から resume までの人の返事は、問いに数えない
    ended = False  # 直前の assistant が turn を終えたか
    for line in transcript_lines(path, deadline):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("isSidechain"):
            continue
        m = r.get("message") if isinstance(r.get("message"), dict) else {}
        content = m.get("content")
        if since is not None and not on:
            at = _iso_epoch(r.get("timestamp"))
            if at is None or at < since:
                continue
            on = True
        if r.get("type") == "assistant":
            for b in content if isinstance(content, list) else []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                if b.get("name") == "Bash" and "autopilot.py" in str(inp.get("command", "")):
                    own[b.get("id")] = True
                if not on:
                    continue
                tools += 1
                if b.get("name") in ("Agent", "Task"):  # 手順の C は前景で起動して結果を読むと約束する
                    agents[b.get("id")] = inp.get("run_in_background") in (False, "false")  # 前景を明示したか（Desktop は文字列で残す）
                if b.get("name") == "AskUserQuestion":
                    counts["承認後に人へ問い"] += 1
                elif b.get("name") == "Bash" and _polls(inp):
                    counts["待ちの poll"] += 1
            ended = m.get("stop_reason") == "end_turn"
            continue
        if r.get("type") != "user":  # Stop hook の押し返しは isMeta の行で届くので、ここでは落とさない
            continue
        res = r.get("toolUseResult") if isinstance(r.get("toolUseResult"), dict) else {}
        for tid, body in _results(content):
            # Desktop は前景を明示しても必ず裏で走らせるので、明示したものは数えない
            if on and tid in agents and res.get("status") == "async_launched" and not (
                    agents[tid] and r.get("entrypoint") == "claude-desktop"):
                counts["裏で走った agent"] += 1
            if not own.get(tid):
                continue
            if not on and since is None and APPROVED_OUT.search(body):
                on = True
            elif on and DONE_OUT.search(body):
                return counts
            elif on and WAIT_OUT.search(body):
                waiting = True
            elif on and RESUME_OUT.search(body):
                waiting = False
        if not on or _results(content):
            continue
        text = _text(content).strip()
        if text.startswith("Stop hook feedback"):
            streak = streak + 1 if tools == 0 else 0
            if streak == EMPTY_BLOCKS:
                counts["空の turn の block"] += 1
        elif text and not r.get("isMeta") and not text.startswith(_NOT_HUMAN) and ended and not waiting:
            counts["承認後に人へ問い"] += 1
        if text:
            tools, ended = 0, False
    return counts if on else None


def anomaly_line(counts):
    hits = [f"{k} {v}" for k, v in counts.items() if v]
    return "、".join(hits) if hits else "なし"
