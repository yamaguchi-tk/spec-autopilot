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


NOT_UTF8 = "ADR を UTF-8 で読めない（UTF-8 で保存し直す）"


def read_adr(path):
    """ADR の本文。UTF-8 で読めなければ None（呼び出し元が ERROR か終了で止める）。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


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
    # park は (kind, op, req) が同じものを重複として捨てるので、行ごとに --op へ退けた段と要件の語を入れて区別する
    cmds = [" ".join(["python3", overnight, "park", shlex.quote(str(d)), "--kind", "other",
                      "--op", shlex.quote(f"{req} の要件の文を直す（{st}・「{word}」）"),
                      "--reason", shlex.quote(f"{st}を退けた。要件の語「{word}」 ADR: {adr_path}"), "--req", req])
            for st, req, word in req_rows]
    return missing, cmds


def consent_check(text):
    """合意の ADR の本文から (ERROR の一覧, NOTE の一覧)。足りない行を ERROR にし、行がそろっていれば、要件の文で退けた行ごとに NOTE を返す。"""
    missing, _ = check(text, "", "")
    if missing:
        return missing, []
    return [], [f"ADR が要件の文で退けた段: {st}・{req}「{word}」。要件の文を直すかは人が決める" for st, req, word in REQ_REJECT.findall(text)]


def consent(ap, d, text, warnings):
    """初回の合意の lint から呼ぶ。spec の `- ADR:` が指すファイルの段の行を見て、ERROR の一覧を返し、NOTE を warnings に足す。ADR が無ければ何もしない（今の「ADR が無い」の文が止める）。"""
    if ap.adr_error(d):
        return []
    adr = ap.ADR_LINE.search(text.split("\n## ", 1)[0]).group(1)
    try:
        body = read_adr(ap.repo_root(d) / adr)
    except OSError as e:  # 読む権限が無い・読めない（rework の入口は変えない）
        return [f"ADR {adr}: ADR を読めない（{e.strerror or type(e).__name__}。読める権限にする）"]
    if body is None:
        return [f"ADR {adr}: {NOT_UTF8}"]
    err, notes = consent_check(body)
    warnings += notes
    return [f"ADR {adr}: {e}" for e in err]


def refuse_if_unfit(adr_file, adr_path, d, reqs=None):
    """足りなければ、足りない行を出して終える。要件の文で退けた行があれば、park のコマンドを出して終える。"""
    text = read_adr(adr_file)
    if text is None:
        sys.exit(f"rework: {NOT_UTF8}")
    missing, cmds = check(text, adr_path, d)
    unknown = sorted({r[1] for r in REQ_REJECT.findall(text)} - set(reqs)) if reqs is not None else []
    if unknown:
        sys.exit(f"rework: {', '.join(unknown)} は spec.md の要件に無い（`- 要件の文で退けた:` の R<n> を直す）")
    if missing:
        sys.exit("rework: ADR に足りない行がある。\n" + "\n".join(f"- {m}" for m in missing))
    if cmds:
        sys.exit("rework: 要件の文で退けた直しがある。作り直しは記録しない。その要件を park に積む（人が要件の文を直すかを決める）:\n"
                 + "\n".join(cmds))
