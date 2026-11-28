"""難しい実装で段（モデルと effort）を上げる梯子。段ごとに agent の定義を分ける
（Agent の起動の model は別名しか受けず、`sonnet` は Sonnet 5.5 ではなく Sonnet 5 に解決されるため）。

段は安い順。effort を先に上げ、それでも足りなければモデルを上げる（Opus は Sonnet の約 9 倍の費用）。
Opus xhigh で 2 回落ちたら、Fable を 1 回だけ試す。Fable でも落ちたら、その要件を park に積む。

手元の設定は SPEC_AUTOPILOT_HOME（無ければ ~/.claude/spec-autopilot）の models.md に、spec の `## モデル` と同じ形の行で置く。
`ladder.py setup`・`show` で書く・見る。init が spec.md を作るときに、実装・評価の行を `## モデル` に写す（梯子は spec の節だけを読む）。
セッション単位の上書きは、同じ置き場の `sessions/<id>.models.md` に同じ行の形で置く（`setup --session`）。役ごとの段は、セッションの上書き → 手元の設定 → 同梱の既定の順（`resolve`）。
相談役・検証役・照合役は梯子に入れず（`ADVISORS`）、models.md の `- 相談:`・`- 検証:`・`- 照合:` の行を SessionStart が読んで使う agent を示す。
"""
import argparse
import fcntl
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import stages

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
# 相談役・検証役・照合役の段（RUNGS と別で、overnight.py raise --role の選択肢に入れない）。役 → 段の名前 → (agent の名前, model, effort)。順は安い順で、先頭が既定
ADVISORS = {
    "advisor": {
        "fable-medium": ("fable-advisor", "fable", "medium"),
        "fable-high": ("fable-advisor-high", "fable", "high"),
        "opus-high": ("fable-advisor-opus", "opus", "high"),
    },
    "checker": {
        "opus-high": ("advice-checker", "opus", "high"),
        "fable-high": ("advice-checker-fable", "fable", "high"),
    },
    "spec_checker": {
        "sonnet-high": ("autopilot-spec-checker", "claude-sonnet-5-5", "high"),
        "opus-high": ("autopilot-spec-checker-opus", "opus", "high"),
    },
}
# 評価役の段を手で上げる合図（判断を含むので機械では検出しない）。実装役は review の巡で自動で上げる
REVIEW_REASON = "判定が決まらない"
SPEC_KEY = {"impl": "実装", "review": "評価"}
CONFIG_KEY = {**SPEC_KEY, "advisor": "相談", "checker": "検証", "spec_checker": "照合"}  # 手元の設定の行の語（spec の `## モデル` は実装・評価だけ）
ROLES = {**RUNGS, **ADVISORS}
TABLE = {CONFIG_KEY[role]: rungs for role, rungs in ROLES.items()}
TRIES_BEFORE_FABLE = 2
ROW = re.compile(r"^- (実装|評価):[ \t]*(\S+)[ \t]*$")
CONFIG_ROW = re.compile(r"^- (実装|評価|相談|検証|照合):[ \t]*(\S+)[ \t]*$")
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


def home_path():
    return Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot")


def config_path():
    return home_path() / "models.md"


def session_path(session):
    """セッションの上書きのファイル。id が無いか、セッション id の形（stages.SESSION_ID）でなければ None。"""
    if not isinstance(session, str) or not stages.SESSION_ID.fullmatch(session):
        return None
    return home_path() / "sessions" / f"{session}.models.md"


def read_config(path=None):
    """手元の設定を読む。(元のバイト列 or None, 読める行 {実装|評価|相談|検証|照合: 段}, 誤りの一覧)。無ければ (None, {}, [])。
    読める行は、受ける段で、同じ役の 1 本目だけ。セッションの上書きも同じ読み方（path を渡す）。"""
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


def resolve(session):
    """役ごとの段を決める 1 か所。(決めた行 {役の語: 段}, 手元の設定の行, セッションの上書きの行, 誤りの一覧 [(層の名前, path, [誤り])])。
    順はセッションの上書き → 手元の設定 → 同梱の既定（行が無い役は同梱の既定。呼ぶ側が先頭の段を使う）。session は id（無ければ None）。
    誤りのあるセッションの上書きは、読める行があっても決めた行に使わない（write_spec が層ごと写さないのと同じ）。3 つ目の over は誤りがあっても読めた行を返し、使うかは呼ぶ側が bad で決める。"""
    path = config_path()
    _, base, errors = read_config(path)
    bad = [("手元の設定", path, errors)] if errors else []
    over = {}
    spath = session_path(session)
    if spath:
        _, over, errors = read_config(spath)
        if errors:
            bad.append(("セッションの上書き", spath, errors))
    used = {} if any(layer == "セッションの上書き" for layer, _, _ in bad) else over
    return {**base, **used}, base, over, bad


def render(rows):
    return "".join(f"- {k}: {rows[k]}\n" for k in CONFIG_KEY.values() if k in rows)


def edit(change, path=None, session=False):
    """ロックの中で読み直し、change(読める行) が返した行だけで書き換える（空なら消す）。壊れていた元の中身は毎回別の名前で残す。
    置き場に書けない（OSError）ときは traceback で落とさず、0 以外で終わる。"""
    path = path or config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name(path.name + ".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return _edit_locked(change, path, session)
    except OSError as e:
        block = next((d for d in [path.parent, *path.parent.parents] if os.path.isfile(d)), None)
        why = f"{block} がファイル" if block else type(e).__name__
        sys.exit(f"{path.parent} に書けない（{why}）。{path} は変えていない")


def _edit_locked(change, path, session):
    raw, rows, errors = read_config(path)
    if errors:
        if raw is None:
            sys.exit("; ".join(errors))
        kept = path.with_name(f"{path.name}.bad-{time.time_ns()}-{os.getpid()}")
        kept.write_bytes(raw)
        if session:  # 誤りのあるセッションの上書きは使わない層なので、読めた行も持ち越さない
            rows = {}
        print(f"NOTE: {path} に誤りがあった（{'; '.join(errors)}）。元の中身を退避した: {kept}。"
              + ("読めた行も持ち越さない" if session else "読めた行だけで続ける"), file=sys.stderr)
    rows = change(dict(rows))
    if not rows:
        path.unlink(missing_ok=True)
        return rows
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(render(rows))
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise
    return rows


def write_spec(src, dst):
    """init が spec.md を作る。実装・評価の行（セッションの上書き → 手元の設定の順）を、雛形の `## モデル` のコメントの後に写す
    （相談・検証・照合の行は写さない。読めない層は写さず NOTE で直し方を出す）。"""
    text = Path(src).read_text(encoding="utf-8")
    _, base, over, bad = resolve(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    for layer, path, errors in bad:
        fix = "`ladder.py setup --session --impl <段> --review <段>` で書き直すか、`ladder.py setup --session --reset` で消す" if layer == "セッションの上書き" else \
            "`ladder.py setup --impl <段> --review <段>` で書き直すか、`ladder.py setup --reset` で消す"
        print(f"NOTE: {layer} {path} に誤りがあるので、その層は spec の `## モデル` に写さない（{'; '.join(errors)}）。直す: {fix}（{Path(__file__).resolve()}）", file=sys.stderr)
    spec_keys = SPEC_KEY.values()
    layers = [(name, rows) for name, rows in (("手元の設定", base), ("セッションの上書き", over)) if name not in {b[0] for b in bad}]
    merged = {}
    for _, rows in layers:
        merged.update({k: v for k, v in rows.items() if k in spec_keys})
    lines = [f"- {k}: {v}" for k, v in merged.items()]
    if lines:
        text = re.sub(r"^(## モデル\n(?:<!--.*?-->\n)?)", lambda m: m.group(1) + "\n".join(lines) + "\n", text, count=1, flags=re.M | re.S)
        used = "・".join(name for name, rows in layers if any(k in spec_keys for k in rows))
        print(f"NOTE: {used}の行を spec の `## モデル` に写した（作った後の spec は設定を変えても変わらない）: {' / '.join(lines)}", file=sys.stderr)
    Path(dst).write_text(text, encoding="utf-8")


def accepted_lines():
    return [f"{CONFIG_KEY[role]}: 受ける段 {'・'.join(rungs)}" for role, rungs in ROLES.items()]


def swap_line(role, rung):
    """相談・検証・照合の段を、今のセッションで使う agent の名前に読み替える 1 行（既定の agent なら読み替え無し）。"""
    default = next(iter(ADVISORS[role].values()))[0]
    agent = ADVISORS[role][rung][0]
    return f"{default} → spec-autopilot:{agent}" if agent != default else None


def cmd_show(a):
    path = config_path()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    _, base, over, bad = resolve(session)
    unused = any(layer == "セッションの上書き" for layer, _, _ in bad)
    base_bad = any(layer == "手元の設定" for layer, _, _ in bad)
    for (role, rungs), line in zip(ROLES.items(), accepted_lines()):
        mine = "使わない（誤りがある）" if unused else over.get(CONFIG_KEY[role], "なし")
        here = base.get(CONFIG_KEY[role], "なし")
        if base_bad and CONFIG_KEY[role] in base and CONFIG_KEY[role] in SPEC_KEY.values():
            here += "（誤りがあるので spec に写さない）"
        print(f"{line} / 既定 {next(iter(rungs))} / 手元の設定 {here} / このセッション {mine}")
    print(f"設定のファイル: {path}")
    spath = session_path(session)
    if spath:
        print(f"セッションのファイル: {spath}")
    for layer, _, errors in bad:
        fix = "`ladder.py setup --session` か `ladder.py setup --session --reset`" if layer == "セッションの上書き" else "`ladder.py setup` か `ladder.py setup --reset`"
        for e in errors:
            print(f"{layer}の誤り: {e}（{fix} で直す）")
    return 0


def cmd_setup(a):
    path = config_path()
    if a.session:
        path = session_path(os.environ.get("CLAUDE_CODE_SESSION_ID"))
        if path is None:
            sys.exit("今のセッションが分からない（CLAUDE_CODE_SESSION_ID が無いか、セッション id の形でない）ので --session は使えない。何も変えていない")
    given = {CONFIG_KEY[r]: v for r in ROLES for v in [getattr(a, r)] if v is not None}
    if a.reset is not None:
        if a.reset != "all" and a.reset not in TABLE or given:
            sys.exit(f"--reset は単独で、役は「{'」「'.join(TABLE)}」だけを渡す")
        keys = list(TABLE) if a.reset == "all" else [a.reset]
        edit(lambda rows: {k: v for k, v in rows.items() if k not in keys}, path, a.session)
        print(f"{'・'.join(TABLE) if a.reset == 'all' else a.reset}が既定に戻った（{'セッションの上書き' if a.session else '設定'}のファイル: {path}）")
        return 0
    bad = [f"{CONFIG_KEY[r]} の段「{v}」" for r in ROLES for v in [getattr(a, r)] if v is not None and v not in ROLES[r]]
    if not given or bad:
        sys.exit(("受けない段: " + "、".join(bad) + "\n" if bad else "--impl か --review か --advisor か --checker か --spec-checker か --reset を渡す\n") + "\n".join(accepted_lines()))
    rows = edit(lambda cur: {**cur, **given}, path, a.session)
    print(f"書いた: {path}\n{render(rows)}", end="")
    if a.session:
        for role in ADVISORS:
            if CONFIG_KEY[role] in rows:
                print(f"読み替え（{CONFIG_KEY[role]}）: {swap_line(role, rows[CONFIG_KEY[role]]) or '既定のまま'}")
        if any(k in rows for k in SPEC_KEY.values()):
            print("実装・評価の上書きは、このセッションで後から init する spec にだけ効く（作った spec は変わらない）")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="ladder.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sp = sub.add_parser("setup")
    for role in ROLES:
        sp.add_argument("--" + role.replace("_", "-"))
    sp.add_argument("--reset", nargs="?", const="all")
    sp.add_argument("--session", action="store_true")
    a = p.parse_args(argv)
    return {"show": cmd_show, "setup": cmd_setup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
