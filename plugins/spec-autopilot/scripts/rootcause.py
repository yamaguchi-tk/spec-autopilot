"""作り直しの ADR が、直し方の段と、それより上の段を退けた理由を書いているかを、行の形だけで見る。
中身が正しいかは見ない（評価役と朝の報告で人が読む）。"""
import re
import shlex
import sys
from pathlib import Path

FIX_ORDER = ("要らなくする", "入力の約束を変える", "設計を変える", "局所の継ぎ足し")  # 上の段から
STAGES = "|".join(FIX_ORDER)
FIX_LINE = re.compile(r"^- 直し方:[ \t]*(\S+)[ \t]*$", re.M)
REJECT = re.compile(rf"^- 退けた:[ \t]*({STAGES})（.+）[ \t]*$", re.M)
REQ_REJECT = re.compile(rf"^- 要件の文で退けた:[ \t]*({STAGES})（(R\d+) の「(.+)」）[ \t]*$", re.M)


def check(text, adr_path, d, reqs=None):
    """(足りない行の一覧, park のコマンドの一覧)。"""
    fixes = FIX_LINE.findall(text)
    if len(fixes) != 1 or fixes[0] not in FIX_ORDER:
        return [f"`- 直し方: <段>` の行がちょうど 1 本要る（段は {' / '.join(FIX_ORDER)} のどれか）"], []
    chosen = FIX_ORDER.index(fixes[0])
    req_rows = REQ_REJECT.findall(text)
    done = set(REJECT.findall(text)) | {r[0] for r in req_rows}
    missing = [f"`- 退けた: {st}（<理由>）` か `- 要件の文で退けた: {st}（R<n> の「<要件の語>」）` の行" for st in FIX_ORDER[:chosen]
               if st not in done]
    overnight = shlex.quote(str(Path(__file__).with_name("overnight.py")))
    by_req = {}  # park は (kind, op, req) が同じものを重複として捨てるので、要件ごとに 1 本にして理由を全部入れる
    for st, req, word in req_rows:
        by_req.setdefault(req, []).append(f"{st}を退けた。要件の語「{word}」")
    cmds = [" ".join(["python3", overnight, "park", shlex.quote(str(d)), "--kind", "other", "--op", shlex.quote("要件の文を直す"),
                      "--reason", shlex.quote(" / ".join(rs) + f" ADR: {adr_path}"), "--req", req])
            for req, rs in by_req.items()]
    return missing, cmds


def refuse_if_unfit(text, adr_path, d, reqs=None):
    """足りなければ、足りない行を出して終える。要件の文で退けた行があれば、park のコマンドを出して終える。"""
    missing, cmds = check(text, adr_path, d)
    unknown = sorted({r[1] for r in REQ_REJECT.findall(text)} - set(reqs)) if reqs is not None else []
    if unknown:
        sys.exit(f"rework: {', '.join(unknown)} は spec.md の要件に無い（`- 要件の文で退けた:` の R<n> を直す）")
    if missing:
        sys.exit("rework: ADR に足りない行がある。\n" + "\n".join(f"- {m}" for m in missing))
    if cmds:
        sys.exit("rework: 要件の文で退けた直しがある。作り直しは記録しない。その要件を park に積む（人が要件の文を直すかを決める）:\n"
                 + "\n".join(cmds))
