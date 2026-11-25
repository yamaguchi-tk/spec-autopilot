"""難しい実装で段（モデルと effort）を上げる梯子。段ごとに agent の定義を分ける
（Agent の起動の model は別名しか受けず、`sonnet` は Sonnet 5.5 ではなく Sonnet 5 に解決されるため）。

段は安い順。effort を先に上げ、それでも足りなければモデルを上げる（Opus は Sonnet の約 9 倍の費用）。
Opus xhigh で 2 回落ちたら、Fable を 1 回だけ試す。Fable でも落ちたら、その要件を park に積む。
"""
import re

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
# 評価役の段を手で上げる合図（判断を含むので機械では検出しない）。実装役は review の巡で自動で上げる
REVIEW_REASON = "判定が決まらない"
SPEC_KEY = {"impl": "実装", "review": "評価"}
TRIES_BEFORE_FABLE = 2
ROW = re.compile(r"^- (実装|評価):[ \t]*(\S+)[ \t]*$")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def parse(section_text):
    """コメントを消した節の行を読む。(行の一覧 [(役の語, 段)], 読めない行の一覧)。"""
    rows, bad = [], []
    for line in COMMENT.sub("", section_text or "").splitlines():
        m = ROW.match(line)
        if m:
            rows.append(m.groups())
        elif line.strip():
            bad.append(line.strip())
    return rows, bad


def spec_rows(section_text):
    return dict(parse(section_text)[0])


def lint(section_text):
    """spec の `## モデル` の節の誤り。書かなければ既定。行は `- 実装: <段>` と `- 評価: <段>` だけを 1 本ずつ受ける。"""
    parsed, bad = parse(section_text)
    errors = [f"モデルの節の行を読めない（`- 実装: <段>` か `- 評価: <段>` だけを書く）: {x}" for x in bad]
    keys = [k for k, _ in parsed]
    errors += [f"モデルの節に `- {k}:` が 2 本以上ある" for k in sorted(set(keys)) if keys.count(k) > 1]
    rows = dict(parsed)
    for role, key in SPEC_KEY.items():
        if key in rows and rows[key] not in RUNGS[role]:
            errors.append(f"モデルの節の `- {key}:` は「{'」「'.join(RUNGS[role])}」のどれか（今は「{rows[key]}」）")
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
