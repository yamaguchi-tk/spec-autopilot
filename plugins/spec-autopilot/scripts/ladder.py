"""難しい実装で段（モデルと effort）を上げる梯子。段ごとに agent の定義を分ける
（Agent の起動の model は別名しか受けず、`sonnet` は Sonnet 5.5 ではなく Sonnet 5 に解決されるため）。

段は安い順。effort を先に上げ、それでも足りなければモデルを上げる（Opus は Sonnet の約 9 倍の費用）。
Opus xhigh で 2 回落ちたら、Fable を 1 回だけ試す。Fable でも落ちたら、その要件を park に積む。

手元の設定は SPEC_AUTOPILOT_HOME（無ければ ~/.claude/spec-autopilot）の models.md に、spec の `## モデル` と同じ形の行で置く。
`ladder.py setup`・`show` で書く・見る。init が spec.md を作るときに、実装・評価の行を `## モデル` に写す（梯子は spec の節だけを読む）。
相談役・検証役は梯子に入れず（`ADVISORS`）、models.md の `- 相談:`・`- 検証:` の行を SessionStart が読んで使う agent を示す。
"""
import argparse
import fcntl
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# 役 → 段の名前 → (agent の名前, model, effort)。順は安い順で、先頭が既定
RUNGS = {
    "impl": {
        "sonnet-high": ("autopilot-implementer", "claude-sonnet-5-5", "high"),
        "opus-medium": ("autopilot-implementer-opus", "opus", "medium"),
        "opus-xhigh": ("autopilot-implementer-opus-xhigh", "opus", "xhigh"),
        "fable": ("autopilot-implementer-fable", "fable", "high"),
    },
    "review": {  # 評価役は既定より下げない
        "opus-high": ("autopilot-reviewer", "opus", "high"),
        "opus-xhigh": ("autopilot-reviewer-xhigh", "opus", "xhigh"),
        "fable": ("autopilot-reviewer-fable", "fable", "high"),
    },
}
# 相談役・検証役の段（RUNGS と別で、overnight.py raise --role の選択肢に入れない）。役 → 段の名前 → (agent の名前, model, effort)。順は安い順で、先頭が既定
ADVISORS = {
    "advisor": {
        "fable-medium": ("fable-advisor", "fable", "medium"),
        "fable-high": ("fable-advisor-high", "fable", "high"),
        "opus-high": ("fable-advisor-opus", "opus", "high"),
    },
    "checker": {
        "opus-high": ("advice-checker", "opus", "high"),
    },
}
# 評価役の段を手で上げる合図（判断を含むので機械では検出しない）。実装役は review の巡で自動で上げる
REVIEW_REASON = "判定が決まらない"
SPEC_KEY = {"impl": "実装", "review": "評価"}
CONFIG_KEY = {**SPEC_KEY, "advisor": "相談", "checker": "検証"}  # 手元の設定の行の語（spec の `## モデル` は実装・評価だけ）
ROLES = {**RUNGS, **ADVISORS}
TABLE = {CONFIG_KEY[role]: rungs for role, rungs in ROLES.items()}
TRIES_BEFORE_FABLE = 2
ROW = re.compile(r"^- (実装|評価):[ \t]*(\S+)[ \t]*$")
CONFIG_ROW = re.compile(r"^- (実装|評価|相談|検証):[ \t]*(\S+)[ \t]*$")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def parse(section_text, row=ROW):
    """コメントを消した節の行を読む。(行の一覧 [(役の語, 段)], 読めない行の一覧)。"""
    rows, bad = [], []
    for line in COMMENT.sub("", section_text or "").splitlines():
        m = row.match(line)
        if m:
            rows.append(m.groups())
        elif line.strip():
            bad.append(line.strip())
    return rows, bad


def spec_rows(section_text):
    return dict(parse(section_text)[0])


def lint(section_text, config=False):
    """spec の `## モデル` の節の誤り。書かなければ既定。行は `- 実装: <段>` と `- 評価: <段>` だけを 1 本ずつ受ける。
    config なら手元の設定 models.md の読み方で、`- 相談: <段>`・`- 検証: <段>` も受ける。"""
    row, words = (CONFIG_ROW, CONFIG_KEY) if config else (ROW, SPEC_KEY)
    parsed, bad = parse(section_text, row)
    allowed = "` か `".join(f"- {k}: <段>" for k in words.values())
    errors = [f"モデルの節の行を読めない（`{allowed}` だけを書く）: {x}" for x in bad]
    keys = [k for k, _ in parsed]
    errors += [f"モデルの節に `- {k}:` が 2 本以上ある" for k in sorted(set(keys)) if keys.count(k) > 1]
    rows = dict(parsed)
    for key in words.values():
        if key in rows and rows[key] not in TABLE[key]:
            errors.append(f"モデルの節の `- {key}:` は「{'」「'.join(TABLE[key])}」のどれか（今は「{rows[key]}」）")
    return errors


def climb(section_text, role, events):
    """始めの段から events の数だけ上げた段の位置。一番上を超えたら None（park）。
    実装役は Opus xhigh で 2 回落ちるまで留まる（Fable は Opus xhigh で 2 回落ちた後だけ）。評価役は 1 回で 1 段上げる。"""
    names = list(RUNGS[role])
    start = spec_rows(section_text).get(SPEC_KEY[role])
    i, tries = (names.index(start) if start in names else 0), 0
    for _ in range(events):
        if role == "impl" and names[i] == "opus-xhigh" and tries + 1 < TRIES_BEFORE_FABLE:
            tries += 1
            continue
        i, tries = i + 1, 0
        if i >= len(names):
            return None
    return i


def impl_agent(section_text, raises, reqs, over=()):
    """(実装役の名前, 一番上を超えた要件)。名前は、超えていない要件の段の最大（残りが無ければ None）。
    over は、ほかの理由（Fable で失敗した）で一番上を超えたとみなす要件。"""
    names = list(RUNGS["impl"])
    tops = {q: climb(section_text, "impl", len([r for r in raises if r.get("role") == "impl" and r.get("req") == q]))
            for q in reqs or [None]}
    past = [q for q, i in tops.items() if i is None or q in over]
    left = [i for q, i in tops.items() if q not in past]
    return (RUNGS["impl"][names[max(left)]][0] if left else None), past


def review_agent(section_text, raises, reviews):
    """評価役。Fable は 1 回だけ試す（Fable に上げた後にレビューを 1 回記録したら Opus xhigh に戻す）。"""
    names = list(RUNGS["review"])
    ups = [r for r in raises if r.get("role") == "review"]
    i = climb(section_text, "review", len(ups))
    if i is None or (names[i] == "fable" and any(float(v["at"]) > float(ups[-1]["at"]) for v in reviews)):
        i = names.index("opus-xhigh")
    return RUNGS["review"][names[i]][0]


def unrecorded_review(d, s):
    """最後の評価役の起動（hook が記録した review_launches）より後に review の記録が無ければ、その旨の文。あれば None。"""
    reviews = s.get("reviews") or []
    if (s.get("review_launches") or [0])[-1] > (reviews[-1]["at"] if reviews else 0):
        return f"{d} は評価役を起動したのに結果が記録されていない。評価役の結果を `autopilot.py review {d} --high ...` で記録してから進む"
    return None


def raise_reason(streak_now, investigate, rework):
    """review の巡で、その要件を 1 段上げる合図。無ければ None（実装役の失敗は fail の記録の時点で上げる）。"""
    if streak_now == rework:
        return "作り直し"
    if streak_now == investigate:
        return "原因調査"
    return None


def report_lines(raises, reviews, rows=None):
    """朝の報告の行。段を上げたタスクの数と、上げた後の最後のレビューで、そのタスクの上げた要件に high が無かった割合。"""
    impl = [r for r in raises if r.get("role") == "impl"]
    if not raises:
        return []
    ok = {}
    for q in {r["req"] for r in impl}:
        last = max(float(r["at"]) for r in impl if r["req"] == q)
        after = [v for v in reviews if float(v["at"]) > last]
        ok[q] = bool(after) and q not in after[-1].get("high", [])
    rows = rows or {}
    tasks = {t: [q for q in qs if q in ok] for t, qs in rows.items() if any(q in ok for q in qs)}
    tasks.update({q: [q] for q in ok if not any(q in qs for qs in tasks.values())})  # タスクに無い要件はそれだけで 1 本
    passed = sum(all(ok[q] for q in qs) for qs in tasks.values())
    lines = [f"- 段を上げたタスク: {len(tasks)}（上げた後のレビューで通った割合 {round(100 * passed / len(tasks)) if tasks else 0}%）"]
    for r in raises:
        who = r["req"] if r.get("role") == "impl" else "評価"
        lines.append(f"  - {who} {r['from']}→{r['to']}（{r['reason']}）")
    return lines


def config_path():
    return Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot") / "models.md"


def read_config(path=None):
    """手元の設定を読む。(元のバイト列 or None, 読める行 {実装|評価|相談|検証: 段}, 誤りの一覧)。無ければ (None, {}, [])。
    読める行は、受ける段で、同じ役の 1 本目だけ。"""
    path = path or config_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, {}, []
    except OSError as e:
        return None, {}, [f"{path} を読めない（{type(e).__name__}）"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw, {}, [f"{path} が UTF-8 で読めない"]
    rows = {}
    for key, rung in parse(text, CONFIG_ROW)[0]:
        if rung in TABLE[key]:
            rows.setdefault(key, rung)
    return raw, rows, lint(text, config=True)


def render(rows):
    return "".join(f"- {k}: {rows[k]}\n" for k in CONFIG_KEY.values() if k in rows)


def edit(change):
    """ロックの中で読み直し、change(読める行) が返した行だけで書き換える（空なら消す）。壊れていた元の中身は毎回別の名前で残す。"""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw, rows, errors = read_config(path)
        if errors:
            if raw is None:
                sys.exit("; ".join(errors))
            kept = path.with_name(f"{path.name}.bad-{time.time_ns()}-{os.getpid()}")
            kept.write_bytes(raw)
            print(f"NOTE: {path} に誤りがあった（{'; '.join(errors)}）。元の中身を退避した: {kept}。読めた行だけで続ける", file=sys.stderr)
        rows = change(dict(rows))
        if not rows:
            path.unlink(missing_ok=True)
            return rows
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(render(rows))
        os.replace(tmp, path)
        return rows


def write_spec(src, dst):
    """init が spec.md を作る。手元の設定の実装・評価の行を、雛形の `## モデル` のコメントの後に写す（相談・検証の行は写さない。読めない設定は写さず NOTE で直し方を出す）。"""
    text = Path(src).read_text(encoding="utf-8")
    path = config_path()
    raw, _, errors = read_config(path)
    if errors:
        print(f"NOTE: 手元の設定 {path} に誤りがあるので、spec の `## モデル` は雛形のまま（{'; '.join(errors)}）。"
              f"直す: `ladder.py setup --impl <段> --review <段>` で書き直すか、`ladder.py setup --reset` で消す（{Path(__file__).resolve()}）", file=sys.stderr)
    elif raw is not None:
        lines = [f"- {k}: {v}" for k, v in parse(raw.decode("utf-8"))[0]]
        if lines:
            text = re.sub(r"^(## モデル\n(?:<!--.*?-->\n)?)", lambda m: m.group(1) + "\n".join(lines) + "\n", text, count=1, flags=re.M | re.S)
            print(f"NOTE: 手元の設定 {path} の行を spec の `## モデル` に写した（作った後の spec は設定を変えても変わらない）: {' / '.join(lines)}", file=sys.stderr)
    Path(dst).write_text(text, encoding="utf-8")


def accepted_lines():
    return [f"{CONFIG_KEY[role]}: 受ける段 {'・'.join(rungs)}" for role, rungs in ROLES.items()]


def cmd_show(a):
    path = config_path()
    _, rows, errors = read_config(path)
    for (role, rungs), line in zip(ROLES.items(), accepted_lines()):
        print(f"{line} / 既定 {next(iter(rungs))} / 手元の設定 {rows.get(CONFIG_KEY[role], 'なし')}")
    print(f"設定のファイル: {path}")
    for e in errors:
        print(f"設定の誤り: {e}（`ladder.py setup` か `ladder.py setup --reset` で直す）")
    return 0


def cmd_setup(a):
    path = config_path()
    given = {CONFIG_KEY[r]: v for r in ROLES for v in [getattr(a, r)] if v is not None}
    if a.reset is not None:
        if a.reset != "all" and a.reset not in TABLE or given:
            sys.exit(f"--reset は単独で、役は「{'」「'.join(TABLE)}」だけを渡す")
        keys = list(TABLE) if a.reset == "all" else [a.reset]
        edit(lambda rows: {k: v for k, v in rows.items() if k not in keys})
        print(f"{'・'.join(TABLE) if a.reset == 'all' else a.reset}が既定に戻った（設定のファイル: {path}）")
        return 0
    bad = [f"{CONFIG_KEY[r]} の段「{v}」" for r in ROLES for v in [getattr(a, r)] if v is not None and v not in ROLES[r]]
    if not given or bad:
        sys.exit(("受けない段: " + "、".join(bad) + "\n" if bad else "--impl か --review か --advisor か --checker か --reset を渡す\n") + "\n".join(accepted_lines()))
    rows = edit(lambda cur: {**cur, **given})
    print(f"書いた: {path}\n{render(rows)}", end="")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="ladder.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sp = sub.add_parser("setup")
    for role in ROLES:
        sp.add_argument(f"--{role}")
    sp.add_argument("--reset", nargs="?", const="all")
    a = p.parse_args(argv)
    return {"show": cmd_show, "setup": cmd_setup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
