#!/usr/bin/env python3
"""spec-autopilot の成果物の検査と状態の記録。

使い方:
  autopilot.py init <slug>                         docs/specs/<日付>-<slug>/ を雛形から作る（phase=discovery）
  autopilot.py lint <dir>                          spec.md の形を検査する（誤りは exit 1、曖昧な語は警告）
  autopilot.py approve <dir> --by <返事の要約>      lint が通れば承認を記録する（phase=building）。壁打ち中・block の後・done の後に受ける
                                                   （done の後は、PR のレビューなどで人に直しを頼まれたとき。done の後の人の発言が要る）
  autopilot.py check <dir> [--stage pr]            要件→タスク→QA の証拠の対応を検査する（既定は範囲の完了条件も見る。
                                                   pr は PR を作る前の検査で、マージ・デプロイ・QA の記録を見ない）
  autopilot.py done <dir>                          check が通れば phase=done にする
  autopilot.py block <dir> --req R<n> --reason .. --evidence ..   満たせない要件を記録する（phase=blocked）
  autopilot.py wait <dir> --reason ..             安全規則の確認を人に求める間、自走を止める（phase=wait）
  autopilot.py resume <dir>                        人の返事の後に自走へ戻す（phase=building）
  autopilot.py adopt <dir>                         自走中・確認待ちの spec をこのセッションが引き継ぐ（以後 Stop hook が止める）
  autopilot.py status <dir>                        phase・予算・梯子・残り・続け方を出す（中断・引き継ぎ・compaction の後に読む）
  autopilot.py active                              自走中（building）の spec のディレクトリを出す
  autopilot.py anomalies <transcript>...           承認から done までの自走の異常を型ごとに数える（知らせるだけで止めない）

人の承認と返事は、UserPromptSubmit hook（hooks/user_prompt.py）が書く記録と、その記録が指す transcript の
origin が human の行の時刻で確かめる（hook は知らせや subagent の報告でも動くので、記録の時刻だけでは決めない）。
origin が無い transcript（headless の claude -p など）では止める。人の役を agent が演じる run だけ、Claude Code を
起動する側が選び、hook が記録に印を書く（README の「前提と制限」）。
approve と resume は、その時刻が spec.md（block・done の後はその時刻、resume は wait）より後のときだけ通る。

行の形だけを読み、形の合わない行は誤りにする（自由文は解釈しない）:
  spec.md   要件 `- R1: ...`、QA の方向性の表の行 `| R1 | ... | ... |`、予算 `- 予算: 30 分`
  tasks.md  `- [x] T1: ... [R1, R2]`
  qa.md     `| R1 | pass|unverified|fail | 証拠 |`。pass の証拠の文法は EVIDENCE_* のコメント
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
ARTIFACTS = ("spec.md", "tasks.md", "qa.md")
SECTIONS = ("目的", "要件", "非目標", "作り方", "QA の方向性", "制約", "止まる条件")
EXISTING_SECTIONS = ("影響範囲", "変えない挙動")  # init の時点でコードがあった repo だけで必須
REGRESSION = re.compile(r"^- 回帰テスト:[ \t]*\S", re.M)
SIZE_LINE = re.compile(r"^- 大きさ:[ \t]*([SML])[ \t]*$", re.M)
SIZE_ANY = re.compile(r"^- 大きさ:.*$", re.M)
_RANGE = r"(?::\d+(?:[-〜～]\d+)?)?"  # 行と行の範囲。影響範囲と前提で同じものを受ける
_PATH = rf"`?(?P<path>[^`\s:（）]+){_RANGE}`?"
_NAME = r"`?[A-Za-z_$][\w$]*(?:[.#][A-Za-z_$][\w$]*)*(?:\(\))?`?"
_INPUT = r"`?[^`\s、（）]+`?"  # 設定キー・環境変数・テーブル名など、変えるコードが読む入力の名前
IMPACT_KINDS = [  # 影響範囲の行の文法（許可リスト）。合わない行は ERROR にし、0 件に数えない。バッククォートは有っても無くても受ける
    ("変える", re.compile(rf"^- 変える:[ \t]*{_PATH}[ \t]*（(?P<names>全体|{_NAME}(?:、{_NAME})*)）[ \t]*$")),
    ("新規", re.compile(rf"^- 新規:[ \t]*{_PATH}[ \t]*$")),
    ("呼び出し元なし", re.compile(r"^- 呼び出し元:[ \t]*なし[ \t]*$")),  # _PATH より先に当てる（`なし` をパスに読まない）
    ("呼び出し元", re.compile(rf"^- 呼び出し元:[ \t]*{_PATH}[ \t]*$")),
    ("別の実装", re.compile(rf"^- 別の実装:[ \t]*{_PATH}[ \t]*$")),
    ("同じ入力", re.compile(rf"^- 同じ入力:[ \t]*(?P<inputs>なし|{_INPUT}(?:、{_INPUT})*)[ \t]*$")),
    ("自由", re.compile(r"^- (?:手本|回帰テスト):[ \t]*\S.*$")),
    ("メモ", re.compile(r"^[ \t]+- メモ:")),
]
PREMISE_ROWS = ("目的に届く", "運用", "普通のやり方", "過去", "前提")  # 前提の節の行の種類。どれも 1 行以上を求める（当たらないなら `なし（<理由>）`）
_HOW_ITEM = rf"`?(?P<p>[^`\s:（）、]+){_RANGE}`?(?:（[^）]*）)?"
_HOW_LIST = _HOW_ITEM.replace("?P<p>", "?:")
_NONE = r"なし（[^）\S]*[^）\s][^）]*）"  # 理由は空白でない字を 1 つ以上（空白だけを読み飛ばし、最初の字で決める）
HOW_ROWS = ("path", "コマンド", "URL", "未確認")  # 確かめ方の種類。書き手が行の頭で宣言し、lint は形から推し量らない
PREMISE_KINDS = [  # 前提の節の行の文法（許可リスト）。合わない行は ERROR にする。確かめ方は `- 前提:` の下に字下げして 1 行に 1 つ
    ("前提なし", re.compile(rf"^- 前提:[ \t]*{_NONE}[ \t]*$")),
    ("前提", re.compile(r"^- 前提:[ \t]*(?!なし)\S.*$")),
    *[(k, re.compile(rf"^- {k}:[ \t]*(?:{_NONE}|(?!なし)\S.*)[ \t]*$")) for k in PREMISE_ROWS[:-1]],  # なしで始まるなら理由の括弧が要る
    ("path", re.compile(rf"^[ \t]+- path:[ \t]*(?P<how>{_HOW_LIST}(?:[ \t]*、[ \t]*{_HOW_LIST})*)[ \t]*$")),
    ("コマンド", re.compile(r"^[ \t]+- コマンド:[ \t]*`[^`\S]*[^`\s][^`]*`[ \t]*→[ \t]*\S.*$")),
    ("URL", re.compile(r"^[ \t]+- URL:[ \t]*https?://[!-~]+[ \t]*$")),
    ("未確認", re.compile(r"^[ \t]+- 未確認:[ \t]*\S.*$")),
    ("メモ", re.compile(r"^[ \t]+- メモ:")),
]
HOW_PATH = re.compile(_HOW_ITEM)
NAME_IN = re.compile(r"[A-Za-z_$][\w$]*(?:[.#][A-Za-z_$][\w$]*)*")
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.[^/]+$|\.(test|spec)\.[^/]+$")
SPEC_FILES = re.compile(r"^docs/(?:specs|adr)/|^\.autopilot-qa/")
NOT_CODE = re.compile(r"(^|/)docs/|^\.autopilot-qa/")  # テストと docs/ の下は数えない。.md は docs/ の外なら数える（skill・agent など .md が本体の repo があるため）
SIZES = "SML"
VAGUE = ("適切", "正しく", "十分", "なるべく", "柔軟", "いい感じ", "使いやすい", "appropriately", "properly")

REQ = re.compile(r"^- (R\d+):\s*(\S.*)$", re.M)
QA_PLAN_ROW = re.compile(r"^\|\s*(R\d+)\s*\|", re.M)
BUDGET = re.compile(r"^- 予算:\s*(\d+)\s*分\s*$", re.M)
TASK = re.compile(r"^- \[( |x|X)\] (T\d+):.*?\[([^\]]*)\]\s*$")
TASK_NOTE = re.compile(r"^\s+- メモ:")
HEADING = re.compile(r"^#{1,6}\s")
QA_HEAD = re.compile(r"^\|\s*要件\s*\|\s*結果\s*\|\s*証拠\s*\|\s*$")
QA_SEP = re.compile(r"^\|[\s|:-]+\|\s*$")
COMMENT = re.compile(r"^\s*<!--.*-->\s*$")
COMMENT_BLOCK = re.compile(r"<!--.*?-->", re.S)
LADDER_INVESTIGATE, LADDER_REWORK, MAX_REWORKS = 2, 3, 2  # references/dead-end.md の段（2 回で調べ、3 回で作り方へ、作り直しは要件ごとに 2 回）
FAIL_SOURCES = ("impl", "qa", "review")
PROMPT_FILE = "spec-autopilot-last-user-prompt"
ADR_LINE = re.compile(r"^- ADR:\s*(\S+)\s*$", re.M)
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")  # 先頭は英数字（見回り役が claude の引数に置くので、option と読まれない形だけを受ける）
QA_ROW = re.compile(r"^\|\s*(R\d+)\s*\|\s*(pass|fail|unverified)\s*\|(.*)\|\s*$")  # 証拠の欄は 1 つの (.*) にし、前後の空白は check で除く（空白の分け方で後戻りしない）
# pass の証拠の欄の文法（許可リスト。agents/autopilot-reviewer.md の出力の節と同じ形）:
#   <テスト>[<区切り><テスト>...][ と cmd: ...][。<文>][（注記）]  か  cmd: ...  か  manual: ...
#   末尾の 1 組の（…）は注記、最初の 。から後ろは文として読まない（文の中に :: があれば落とす）
#   テストは <path>::<名前>[::<名前>...]。path を省いた ::<名前> は直前の path を使う。名前は全部ファイルの中に要る
EVIDENCE_FREE = re.compile(r"(?:^|(?<=[\s・、,。]))(?:cmd|manual):")  # ここから後ろは自由文（中の :: は見ない）
EVIDENCE_SEP = re.compile(r"[・、,](?=\s*`?[^\s・、,:（）`]*::)")  # 直後がテストのときだけ区切る（jest の名前の中の 、では区切らない）
EVIDENCE_PARAM = re.compile(r"\[[^\]]*\]$")  # pytest の parametrize の id
EVIDENCE_FORMS = "形が読めない（`<path>::<テスト名>` を `・` で並べ、続けて ` と cmd: ...` か、`cmd: ...`・`manual: ...`）"


def repo_root(start):
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start, capture_output=True, text=True)
    except OSError:
        return Path(start)
    return Path(out.stdout.strip()) if out.returncode == 0 else Path(start)


def load_state(d):
    return json.loads((d / "state.json").read_text(encoding="utf-8"))


def save_state(d, s):
    s["last_active_at"] = time.time()  # 中断の後の再開で、止まっていた時間を予算から外すために残す
    tmp = d / f".state.json.{os.getpid()}"  # 書きかけを Stop hook に読ませない（読めない spec は続行中に放される）
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, d / "state.json")


OWN_ADR = "\0ADR\0"  # 本文に素では書けない置き換え記号
ADR_NUMBER = re.compile(r"(?!\d{4}-\d{2}-\d{2}-)(\d+)-")  # 連番の ADR のファイル名の番号。日付の名前は番号と読まない


def head_and_body(text):
    """spec を、最初の `## ` より前（先頭）と、それ以降（作り方の節を除く本文）に分ける。"""
    head, _, body = text.partition("\n## ")
    body = "\n## " + body if body else ""
    how = section(body, "作り方")
    if how is not None:
        body = body.replace(how, "\n", 1)
    return head, body


def sha(d):
    """承認の対象のハッシュ。作り方の節は、自走中に作り直してよい（ADR に残す）ので外す。
    先頭の `- ADR:` 行の連番の桁は、並行の branch との番号の取り合いで改番されるので外す（ディレクトリと slug は残す）。
    本文は正規化しない。本文が自分の連番の ADR を名前・番号で書くのは lint が承認の前に止める。ADR があるかは check が確かめる。"""
    head, body = head_and_body((d / "spec.md").read_text(encoding="utf-8"))

    def numberless(m):
        folder, name = os.path.split(m.group(1))
        number = ADR_NUMBER.match(name)
        return m.group(0).replace(m.group(1), os.path.join(folder, OWN_ADR + name[number.end(1):])) if number else m.group(0)

    return hashlib.sha256((ADR_LINE.sub(numberless, head) + body).encode("utf-8")).hexdigest()


def own_adr_words(text):
    """本文（作り方の節を除く）が自分の連番の ADR を指す語（ファイル名か `ADR-<番号>`）。改番で書き換わり承認が外れるので lint が止める。"""
    head, body = head_and_body(text)
    adr = ADR_LINE.search(head)
    number = adr and ADR_NUMBER.match(os.path.basename(adr.group(1)))
    if not number:
        return []
    name = os.path.basename(adr.group(1))
    found = [name] if name in body else []
    return found + re.findall(rf"ADR-0*{int(number.group(1))}(?!\d)", body)


def adr_error(d):
    """spec の先頭の `- ADR:` 行と、それが指すファイルを確かめ、足りなければ理由を返す。"""
    adr = ADR_LINE.search((d / "spec.md").read_text(encoding="utf-8").split("\n## ", 1)[0])
    if not adr:
        return "spec.md の先頭に `- ADR: docs/adr/<file>.md` が無い"
    if not (repo_root(d) / adr.group(1)).is_file():
        return f"ADR {adr.group(1)} が無い"
    return None


def git_dir(start):
    out = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=start, capture_output=True, text=True)
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def prompt_file(session):
    """セッションごとの、人の最後の発言の記録。"""
    f = session_file(session)
    return f.with_suffix(".prompt.json") if f else None


def prompt_record(d):
    """人の最後の発言の記録（dict）。記録が無い・読めなければ {}。

    Claude Code の Bash では、自分のセッション（CLAUDE_CODE_SESSION_ID）の発言だけを読む。cwd がどこでも同じ記録を
    読み、同じ repo の別のセッションの発言は数えない。環境変数が無いときだけ、spec の worktree の git dir の記録を読む。
    """
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    f = prompt_file(session) if session else None
    if f is None and not session:
        g = git_dir(d)
        f = g / PROMPT_FILE if g else None
    try:
        rec = json.loads(f.read_text(encoding="utf-8")) if f else {}
        return rec if isinstance(rec, dict) else {}
    except (OSError, ValueError):
        return {}


def last_user_prompt(d):
    """(時刻, session_id) を返す。記録が無い・読めなければ (None, None)。"""
    rec = prompt_record(d)
    try:
        return float(rec["at"]), os.environ.get("CLAUDE_CODE_SESSION_ID") or rec.get("session_id")
    except (KeyError, TypeError, ValueError):
        return None, None


def _human_row(o):
    """transcript の行が人の発言か。host が書く origin.kind が human のものだけを受ける（許可リスト）。
    入力中に打った発言は user 行、作業中に送った発言は queued_command の attachment に残る。"""
    if not isinstance(o, dict) or o.get("isSidechain") or o.get("isMeta"):
        return False
    if o.get("type") == "user":
        content = (o.get("message") or {}).get("content") if isinstance(o.get("message"), dict) else None
        if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        origin = o.get("origin")
    elif o.get("type") == "attachment" and isinstance(o.get("attachment"), dict) and o["attachment"].get("type") == "queued_command":
        origin = o["attachment"].get("origin")
    else:
        return False
    return isinstance(origin, dict) and origin.get("kind") == "human"


def human_said_at(path):
    """transcript の、人の最後の発言の時刻。host が origin をどの行にも書いていなければ（headless の claude -p など）
    None を返す。読めなければ例外を投げる。"""
    last, has_origin = 0.0, False
    for line in transcript_lines(path):
        if '"origin"' not in line:
            continue
        o = json.loads(line)
        has_origin = has_origin or isinstance(o.get("origin"), dict) or isinstance((o.get("attachment") or {}).get("origin"), dict)
        if _human_row(o):
            at = _iso_epoch(o.get("timestamp"))
            last = max(last, at or 0.0)
    return last if has_origin else None


def require_user_after(d, since, what):
    """人の発言の後でなければ止める。承認を実行しているセッション（環境変数が無ければ発言したセッション）の id を返す。

    UserPromptSubmit hook は、background の終わりの知らせや subagent の報告でも動くので、hook の記録だけでは人の発言と
    分からない。記録が指す transcript の、origin が human の行の時刻で確かめる。host が origin をどの行にも書かない
    transcript では見分けられないので止める。人の役を別の agent が演じる run だけは、hook が記録に書いた印（trust が
    true）があれば、記録の時刻で確かめる。印は hook が自分の環境（Claude Code を起動した側）で書くので、agent が
    Bash でこの CLI に環境変数を立てても通らない。"""
    at, session = last_user_prompt(d)
    if at is None or at <= since:
        sys.exit(f"{what}の後に人の発言が記録されていない。人に示して返事を受けてから実行する")
    path = prompt_record(d).get("transcript_path")
    try:
        human = human_said_at(path) if isinstance(path, str) and path else None
        if not isinstance(path, str) or not path:
            raise ValueError("transcript の場所が記録されていない")
    except (OSError, ValueError, AttributeError, TypeError) as e:
        sys.exit(f"人の発言を transcript で確かめられない（{type(e).__name__}）。人に示して返事を受けてから実行する")
    if human is None:
        if prompt_record(d).get("trust") is True:
            return session
        sys.exit("transcript に発言の出どころ（origin）が無いので、人の発言か確かめられない（headless の claude -p など）。"
                 "対話のセッションで人の返事を受けてから実行する")
    if human <= since:
        sys.exit(f"{what}の後に人の発言が記録されていない（届いたのは知らせ・subagent の報告だけ）。人に示して返事を受けてから実行する")
    return session


def session_file(session):
    """セッションごとの、自走させる spec の絶対パスの記録。Stop hook は cwd によらずこれを読む。"""
    if not isinstance(session, str) or not SESSION_ID.fullmatch(session):
        return None
    home = Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot")
    return home / "sessions" / f"{session}.json"


def recorded_specs(session):
    """記録した spec のディレクトリ。記録が無ければ []、壊れていれば例外を投げる。"""
    f = session_file(session)
    if f is None or not f.exists():
        return []
    paths = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(paths, list) or not all(isinstance(x, str) for x in paths):
        raise ValueError(f"{f} の形が読めない")
    return [Path(x) for x in paths]


def record_spec(d, session):
    """spec をセッションの記録に足す。セッションが分からなければ False。"""
    f = session_file(session)
    if f is None:
        return False
    try:
        paths = [str(x) for x in recorded_specs(session)]
    except (OSError, ValueError):
        paths = []
    if str(d.resolve()) not in paths:
        paths.append(str(d.resolve()))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def release(d):
    """done・block の後に、このセッション（CLAUDE_CODE_SESSION_ID）の記録から spec を外す（take_over の対）。
    外せないときは記録を残して NOTE を出す（残るのは止める側。壊れた記録は書き直さない）。"""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    f = session_file(session)
    try:
        if f is None:
            raise ValueError("セッションの id が無い")
        paths = [str(x) for x in recorded_specs(session)]
        if str(d.resolve()) in paths:
            paths.remove(str(d.resolve()))
            tmp = f.with_name(f.name + ".tmp")
            tmp.write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(f)
    except (OSError, ValueError) as e:
        print(f"NOTE: このセッションの spec の記録から外せなかった（{type(e).__name__}）。spec のディレクトリが消えると Stop hook が 1 回止める")


def take_over(d, session, what):
    """自走を引き受けるセッションの記録に spec を足す。足せなければ state を変えずに止める（記録の無い自走は Stop hook が止めない）。"""
    try:
        ok = record_spec(d, session)
    except OSError as e:
        sys.exit(f"このセッションの spec の記録を書けない（{type(e).__name__}）ので{what}しない")
    if not ok:
        sys.exit(f"{what}したセッションが分からない（CLAUDE_CODE_SESSION_ID も発言の記録の session_id も無い）ので{what}しない")


def section(text, name):
    m = re.search(rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def classify(text, kinds):
    """全行を、空行・1 行のコメント・kinds（名前→正規表現）のどれか 1 つに分ける。
    (受けた行の (名前, match) の一覧, 分けられない行の一覧) を返す。読み飛ばしは kinds の宣言だけで決まる。"""
    kept, bad = [], []
    for line in text.splitlines():
        if not line.strip() or COMMENT.match(line):
            continue
        for name, pattern in kinds:
            m = pattern.match(line)
            if m:
                kept.append((name, m))
                break
        else:
            bad.append(line.strip())
    return kept, bad


def requirement_lines(text):
    """要件の節を読み、(要件の (id, 本文) の一覧, 読めない行の一覧) を返す。"""
    kept, bad = classify(section(text, "要件") or "", [("req", REQ)])
    return [m.groups() for _, m in kept], bad


def requirements(text):
    return dict(requirement_lines(text)[0])


def git_lines(root, *args):
    """git の出力を NUL 区切りで読む。失敗したら例外を投げる（数えられないまま通さない）。"""
    out = subprocess.run(["git", "-c", "core.quotePath=false", args[0], "-z", *args[1:]], cwd=root, capture_output=True, text=True)
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} が {out.returncode} で終わった")
    return [f for f in out.stdout.split("\0") if f]


def counted(path):
    return not TEST_PATH.search(path) and not NOT_CODE.search(path)


def at_start(root, start, *args):
    """start の commit に当てた git が 0 で終わったら True。1 と、128 で「無い」を表す句のときは False。それ以外は例外を投げる。"""
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"})  # 下の stderr の英語の句で読むため
    if out.returncode not in (0, 1, 128) or (out.returncode == 128 and "Not a valid object name" not in out.stderr
                                               and "does not exist" not in out.stderr and "exists on disk" not in out.stderr):
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} が {out.returncode} で終わった")
    return out.returncode == 0


def impact(root, start, text, commit=True):
    """影響範囲の行を許可リストで読み、init の時点（start）の commit と突き合わせる。(書いたもの, ERROR の一覧) を返す。
    commit が偽なら突き合わせを外し、行の形と必須の行だけを見る（依る spec の承認。着手のときに当て直す）。"""
    def found(*args):
        return at_start(root, start, *args) if commit else None
    rows, bad = classify(text, IMPACT_KINDS)
    errors = [f"影響範囲の行の形が読めない（`- 変える: <path>:<行>（<名前>、…）` か `（全体）`、`- 新規: <path>`、"
              f"`- 呼び出し元: <path>:<行>` か `なし`、`- 別の実装: <path>:<行>`、`- 同じ入力: <名前>、…` か `なし`、`- 手本:`、`- 回帰テスト:`、`  - メモ:` の形で 1 行に 1 つ）: {line}"
              for line in bad]
    decl = {"paths": set(), "callers": set(), "names": set(), "others": set(), "inputs": set()}
    none_said = False
    for role, m in rows:
        if role in ("自由", "メモ", "呼び出し元なし"):
            continue
        if role == "同じ入力":
            if m.group("inputs") == "なし":
                none_said = True
                continue
            for name in m.group("inputs").replace("`", "").split("、"):
                if found("grep", "-q", "-w", "-F", "-e", name, start) is not False:
                    decl["inputs"].add(name)
                else:
                    errors.append(f"`- 同じ入力:` の名前 {name} が、init の時点の commit のどこにも無い（新しく作る入力なら `なし` と書く）")
            continue
        path = os.path.normpath(m.group("path"))
        exists = found("cat-file", "-e", f"{start}:{path}")
        if role == "新規":
            if exists:
                errors.append(f"`- 新規:` の {path} は init の時点の commit にもうある（`- 変える:` に書く）")
            decl["paths"].add(path)
            continue
        if exists is False:
            errors.append(f"`- {role}:` の {path} が init の時点の commit に無い（新しく作るなら `- 新規:` に書く）")
            continue
        if role == "変える":
            decl["paths"].add(path)
            if m.group("names") != "全体":
                for name in {n.split(".")[-1].split("#")[-1] for n in NAME_IN.findall(m.group("names"))}:
                    if found("grep", "-q", "-w", "-F", "-e", name, start, "--", path) is not False:
                        decl["names"].add(name)
                    else:
                        errors.append(f"`- 変える:` の名前 {name} が、init の時点の commit の {path} の中に無い")
        elif role == "呼び出し元":
            decl["callers"].add(path)
        else:
            decl["others"].add(path)
    if not decl["paths"]:
        errors.append("既存の repo では「## 影響範囲」に `- 変える:` か `- 新規:` の行を書く")
    if not none_said and not any(role == "同じ入力" for role, _ in rows):
        errors.append("既存の repo では「## 影響範囲」に `- 同じ入力: <名前>、…`（変えるコードが読む設定キー・環境変数・テーブル名など。無ければ `なし`）の行を書く")
    if none_said and any(role == "同じ入力" and m.group("inputs") != "なし" for role, m in rows):
        errors.append("`- 同じ入力:` に `なし` と名前を両方書いている（どちらかにする）")
    roles = {role for role, _ in rows}
    if not roles & {"呼び出し元", "呼び出し元なし"}:  # 変えたファイルの名前では grep しないので、書き漏れを行の有無で止める
        errors.append("既存の repo では「## 影響範囲」に `- 呼び出し元: <path>:<行>`（変えるファイル・関数を使うほかのファイル。無ければ `- 呼び出し元: なし`）の行を書く")
    if {"呼び出し元", "呼び出し元なし"} <= roles:
        errors.append("`- 呼び出し元:` に `なし` とパスを両方書いている（どちらかにする）")
    return decl, errors


def main_only(root, start, tip):
    """統合先（origin/HEAD）だけが変え、今の中身（tip か作業ツリー）が統合先と同じファイルの集合。統合先を取り込んだ・載せ替えた分を数えないために使う。
    統合先を引けないときは空（init の時点からの差分を全部数える側に倒す）。この branch がもう統合先に入った後は自分の変更も外れるが、
    それは手順の外（マージ済みの PR の直しは CLI init で新しい spec にする）で、早送りの取り込みと見分けられない（見分けずに承認の門を止める側に置く）。"""
    def rev(*args):
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else ""
    here = tip or "HEAD"
    ref = rev("rev-parse", "--verify", "--quiet", "refs/remotes/origin/HEAD^{commit}")
    if not ref:
        return set()
    base0 = rev("merge-base", start, ref)  # 統合先の線の上で、init の時点より前の点（stacked なら前の spec の分岐点）
    if not base0:
        return set()
    out = set()
    for merged in {rev("merge-base", here, ref), ref} - {""}:  # 取り込んだ点と、統合先の先端（取り込みの途中や squash の形）
        mine = set(git_lines(root, "diff", "--name-only", merged, *([tip] if tip else [])))
        out |= set(git_lines(root, "diff", "--name-only", base0, merged)) - mine
    return out


def diff_size(root, start, tip, decl):
    """init の時点（start）からの差分で (大きさ, 数の dict, 差分のファイルの数) を返す。統合先だけが変えたファイル（main_only）は数えない。tip が無ければ作業ツリーと、git がまだ追っていないファイルまでを数える。
    変えたファイルには影響範囲の変える・新規のパス（テストと docs/ の下を除く）を、呼び出し元には、変える関数の名前を含むファイルと、
    影響範囲の呼び出し元のパスを足す（変えたファイルの名前〔main・app など〕は、無関係のファイルにも当たるので grep しない）。別の実装は、同じ入力の名前を含むほかのファイルと、影響範囲の別の実装のパス（どれも数を増やす側だけに働く）。
    git が失敗したら例外を投げる。"""
    theirs = main_only(root, start, tip)
    if tip:
        files = [f for f in git_lines(root, "diff", "--name-only", start, tip) if f not in theirs]
    else:
        files = ([f for f in git_lines(root, "diff", "--name-only", start) if f not in theirs]
                 + git_lines(root, "ls-files", "--others", "--exclude-standard"))
    diffed = {f for f in files if not SPEC_FILES.search(f) and (counted(f) or f in decl["paths"])}  # 試作の有無は、数えるファイルか、影響範囲に書いたパスの差分で決める
    changed = {f for f in diffed | decl["paths"] if counted(f)}
    def grep(words):
        hits = set()
        for word in sorted(words):
            found = git_lines(root, "grep", "-l", "-w", "-F", "-e", word, *([tip] if tip else []))
            hits |= {f.split(":", 1)[1] if tip else f for f in found}
        return hits
    callers = {f for f in grep(decl["names"]) if f not in changed and counted(f)} | (decl["callers"] - changed)
    others = ({f for f in grep(decl["inputs"]) if counted(f)} | decl["others"]) - changed - callers
    counts = {"変える": len(changed), "呼び出し元": len(callers), "別の実装": len(others)}
    if counts["変える"] >= 6:
        size = "L"
    elif counts["変える"] <= 1 and counts["呼び出し元"] + counts["別の実装"] <= 2:
        size = "S"
    else:
        size = "M"
    return size, counts, len(diffed)


def counted_size(d, text, tip=None):
    """(大きさ, 差分のファイルの数, 説明, 影響範囲の ERROR の一覧) を返す。git が失敗したときは RuntimeError を投げる。"""
    start = load_state(d).get("start")
    if not start:
        raise RuntimeError("init の時点の commit が state.json に無い（init し直す）")
    root = repo_root(d)
    try:
        decl, errors = impact(root, start, text)
        size, counts, diffed = diff_size(root, start, tip, decl)
    except (OSError, RuntimeError) as e:
        raise RuntimeError(f"差分を数えられない（git が失敗した: {e}）") from e
    return size, diffed, f"数えた大きさ {size}（" + "・".join(f"{k} {v}" for k, v in counts.items()) + "）", errors


SPLIT_L = "大きさ L の spec は 1 本のまま合意しない。呼び出しの関係でまとまるファイルの塊ごとに spec を分け、それぞれを S か M にする"
SPLIT_PR = "大きさが L になった。PR は 1 本にせず、呼び出しの関係でまとまるファイルの塊ごとに stacked PR に分ける"


def stated_size(constraints):
    """「## 制約」の大きさの行を読み、(大きさ, ERROR) を返す。行が無ければ (None, None)。1 行だけで `- 大きさ: <S|M|L>` の形のものだけを受ける。"""
    lines = SIZE_ANY.findall(constraints)
    if not lines:
        return None, None
    if len(lines) > 1:
        return None, f"大きさの行が {len(lines)} 行ある（`- 大きさ: <S|M|L>` を 1 行だけ書く）"
    m = SIZE_LINE.match(lines[0])
    if not m:
        return None, f"大きさの行の形が読めない（`- 大きさ: <S|M|L>` だけを書く）: {lines[0]}"
    return m.group(1), None


def size_errors(d, impact_text, stated, first_agreement, at_approve):
    """既存の repo の、申告した大きさと数えた大きさを突き合わせる。(errors, warnings) を返す。大きさは申告と数えた大きさの大きい側だけで決め、人の発言では小さくしない。L は初回の合意（first_agreement）でだけ止める。"""
    if stated is None:
        return ["既存の repo では「## 制約」に `- 大きさ: <S|M|L>` を書く"], []
    try:
        size, diffed, detail, errors = counted_size(d, impact_text)
    except RuntimeError as e:
        return [str(e)], []
    if errors:
        return errors, []
    if first_agreement and "L" in (stated, size):  # 合意し直しでは L を理由には止めない。実装はもう同じブランチにあり、spec を分けても PR は分かれない。PR は done の NOTE で分けさせる
        return [f"{SPLIT_L}（申告 {stated}・{detail}）"], []
    if stated == "S" and diffed == 0:
        if at_approve:
            return ["大きさ S を確かめる試作の差分が無い。承認の前に試作を作って数えるか、大きさを M 以上にする"], []
        return [], [f"大きさ S は試作の差分がまだ無いので確かめていない（試作を作ったら lint を回し直す）。{detail}"]
    if SIZES.index(stated) >= SIZES.index(size):
        return [], [detail]
    return [f"大きさ {stated} は{detail}より小さい。「## 制約」を `- 大きさ: {size}` に直し、予算と実装の分け方も合わせる"], []


def lint(d, at_approve=False, preflight=False, base=None, ahead=0):
    """(errors, warnings) を返す。base が偽なら init の時点との突き合わせを外し、書式だけを見る（依る spec の着手で回す）。
    base が None なら、着手の前の依る spec（「## 制約」に `- 依る spec:`）だけ外す。ahead は前に並ぶ spec の分。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    if base is None:
        base = not (load_state(d).get("phase") in ("discovery", "queued") and __import__("lineup").after_name(d))
    errors, warnings = [], []
    for name in SECTIONS:
        if section(text, name) is None:
            errors.append(f"spec.md に「## {name}」の節が無い")
    pairs, bad = requirement_lines(text)
    for line in bad:
        errors.append(f"要件の行の形が読めない（`- R1: ...` の形で書く）: {line}")
    ids = [rid for rid, _ in pairs]
    for rid in sorted({r for r in ids if ids.count(r) > 1}):
        errors.append(f"{rid} が要件に 2 回以上ある")
    reqs = dict(pairs)
    if not reqs:
        errors.append("要件が無い（「## 要件」に `- R1: ...` の形で書く）")
    planned = set(QA_PLAN_ROW.findall(section(text, "QA の方向性") or ""))
    for rid in reqs:
        if rid not in planned:
            errors.append(f"{rid} の確かめ方が「## QA の方向性」の表に無い")
    import overnight
    if overnight.budgets(text)[0] is None:
        errors.append("予算が無い（「## 制約」に `- 予算: <分> 分` の形で書く）")
    premise_text = COMMENT_BLOCK.sub("", section(text, "前提") or "")
    if not premise_text.strip():
        errors.append("「## 前提」を書く（目的に届くか・運用・普通のやり方・過去・既存の振る舞いについての前提）")
    else:
        errors += __import__("premises").check(sys.modules[__name__], repo_root(d), load_state(d).get("start"), premise_text, commit=base)
    constraints = COMMENT_BLOCK.sub("", section(text, "制約") or "")
    stated, size_err = stated_size(constraints)
    errors += ([size_err] if size_err else []) + __import__("playbooks").lint(constraints)
    first_agreement = load_state(d).get("phase") in ("discovery", "queued")
    if load_state(d).get("existing"):
        body = {name: COMMENT_BLOCK.sub("", section(text, name) or "") for name in EXISTING_SECTIONS}
        for name in EXISTING_SECTIONS:
            if not body[name].strip():
                errors.append(f"既存の repo では「## {name}」を書く")
        if not REGRESSION.search(body["影響範囲"]):
            errors.append("既存の repo では「## 影響範囲」に `- 回帰テスト: <関係するテストを回すコマンド>` を書く")
        if not size_err and base:
            more_err, size_warn = size_errors(d, body["影響範囲"], stated, first_agreement, at_approve)
            errors += more_err
            warnings += size_warn
        elif not size_err:  # 依る spec の承認: 数えるのは着手のとき。行の形と申告だけを見る
            errors += impact(repo_root(d), None, body["影響範囲"], commit=False)[1]
            errors += ["既存の repo では「## 制約」に `- 大きさ: <S|M|L>` を書く"] if stated is None else []
            errors += [SPLIT_L] if first_agreement and stated == "L" else []
    elif first_agreement and stated == "L":
        errors.append(SPLIT_L)
    for word in sorted(set(own_adr_words(text))):
        errors.append(f"本文が自分の ADR を「{word}」で指している。ADR の番号は並行の branch と取り合って改番されるので、"
                      "本文では「この spec の ADR」と書く（作り方の節では書いてよい）")
    import overnight  # 範囲と段の規則は PR の後のループと一緒に置く（このファイルの行の予算のため）
    import stages
    errors += stages.lint(sys.modules[__name__], text, reqs) + __import__("ladder").lint(section(text, "モデル"))
    more_err, more_warn = overnight.scope_lint(text)
    pre_err, pre_warn = __import__("preflight").check(text, time.time() + ahead * 60) if at_approve or preflight else ([], [])  # 夜通しの前提は人がいる lint と承認のとき
    errors += more_err + pre_err
    warnings += more_warn + pre_warn
    for rid, body in reqs.items():
        for word in VAGUE:
            if word in body:
                warnings.append(f"{rid} に曖昧な語「{word}」がある。確かめられる形に直すとよい")
    return errors, warnings


MAX_ARTIFACT_BYTES = 200_000  # check が解析する qa.md・tasks.md の大きさの上限
MAX_ARTIFACT_LINE = 4_000  # 1 行の字数の上限（実データの証拠の欄の最長は 482 字）。TASK は行の長さの 2 乗の時間がかかる
MAX_EVIDENCE_FILE = 2_000_000  # 証拠が指すファイルの大きさの上限
MAX_EVIDENCE_SCAN = 256_000_000  # 1 回の check で、証拠の名前を探すために走査するバイト数の合計の上限


def read_capped(f, limit):
    """上限 +1 バイトまでだけ読む（読む前に全量を読まない）。上限を超えていれば None を返す。"""
    with open(f, "rb") as h:
        data = h.read(limit + 1)
    return None if len(data) > limit else data


def bounded(d, name, errors):
    """成果物を読み、上限を超える分を ERROR にして、解析してよい行だけを返す（Stop hook の timeout より前に終えるため）。"""
    data = read_capped(d / name, MAX_ARTIFACT_BYTES)
    if data is None:
        errors.append(f"{name} が大きすぎる（{MAX_ARTIFACT_BYTES:,} バイトまで）。解析していない")
        return ""
    lines = []
    for i, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if len(line) > MAX_ARTIFACT_LINE:
            errors.append(f"{name} の {i} 行目が長すぎる（{len(line):,} 字。{MAX_ARTIFACT_LINE:,} 字まで）。解析していない")
        else:
            lines.append(line)
    return "\n".join(lines)


def check(d, stage="all"):
    """(errors, notes) を返す。stage="pr" は PR を作る前の検査（範囲の完了条件〔マージ・デプロイ・QA〕を見ない）。"""
    s = load_state(d)
    if s.get("phase") not in ("building", "done"):
        return [f"承認されていない（phase={s.get('phase')}）"], []
    errors, notes = [], []
    if sha(d) != s.get("spec_sha256"):
        errors.append("spec.md の要件・QA の方向性・制約などが承認の後に変わった。"
                      "spec.md を承認の時点に戻す。1 つの要件だけを変える必要があるなら `overnight.py park` でその要件を積む。"
                      "どの要件も進められないときだけ block する（作り方の節と、先頭の `- ADR:` 行の番号〔改番〕は変えてよい）")
    adr = adr_error(d)
    if adr:
        errors.append(f"{adr}（ADR を改番したなら、先頭の `- ADR:` 行をファイルの名前に合わせる）")
    reqs = requirements((d / "spec.md").read_text(encoding="utf-8"))
    covered, count = set(), 0
    kept, bad = classify(bounded(d, "tasks.md", errors),
                         [("head", HEADING), ("note", TASK_NOTE), ("task", TASK)])
    for line in bad:
        errors.append(f"tasks.md の行の形が読めない（`- [x] T1: ... [R1]` か、タスクの下の `  - メモ: ...` で書く）: {line}")
    for name, m in kept:
        if name != "task":
            continue
        count += 1
        mark, tid, refs = m.groups()
        if mark == " ":
            errors.append(f"{tid} が終わっていない")
        covered.update(r.strip() for r in refs.split(",") if r.strip())
    if not count:
        errors.append("tasks.md にタスクが無い（`- [ ] T1: ... [R1]` の形で書く）")
    for rid in reqs:
        if rid not in covered:
            errors.append(f"{rid} を受け持つタスクが tasks.md に無い")
    rows = {}
    kept, bad = classify(bounded(d, "qa.md", errors),
                         [("head", HEADING), ("table_head", QA_HEAD), ("sep", QA_SEP), ("row", QA_ROW)])
    for line in bad:
        errors.append(f"qa.md の行の形が読めない（`| R1 | pass か fail か unverified | 証拠 |` で書く）: {line}")
    for name, m in kept:
        if name != "row":
            continue
        if m.group(1) in rows:
            errors.append(f"qa.md に {m.group(1)} の行が 2 本ある。最新の結果の 1 行にする")
        else:
            rows[m.group(1)] = (m.group(2), m.group(3).strip())
    root = repo_root(d)
    seen = {"texts": {}, "found": set(), "scanned": 0}  # 1 回の check の中で、証拠のファイルを 1 回だけ読み、同じ名前を 1 回だけ探す
    for rid in reqs:
        if rid not in rows:
            errors.append(f"{rid} の QA の結果が qa.md に無い")
            continue
        result, evidence = rows[rid]
        if result == "unverified":
            if evidence:
                notes.append(f"{rid} は unverified（{evidence}）。PR 本文に書き、充足を主張しない")
            else:
                errors.append(f"{rid} は unverified だが理由が無い")
        elif result != "pass":
            errors.append(f"{rid} の QA の結果が {result}")
        else:
            problem = evidence_problem(root, evidence, seen)
            if problem:
                errors.append(f"{rid} の証拠: {problem}")
    import overnight
    errors += ladder_errors(s) + overnight.review_errors(d, s)
    errors += overnight.stage_errors(d, s, {r: rows[r] for r in reqs if r in rows}, stage)
    return errors + (overnight.scope_errors(d, s) if stage != "pr" else []) + __import__("light").errors(d, s), notes


def ladder_errors(s):
    """レビューの記録と、行き詰まりの梯子（references/dead-end.md）の段を検査する。"""
    errors = []
    reviews = s.get("reviews") or []
    if not reviews:
        errors.append("最後のレビューが記録されていない（autopilot-reviewer を回し、autopilot.py review で記録する）")
    elif reviews[-1]["high"]:
        errors.append(f"最後のレビューに high（{', '.join(reviews[-1]['high'])}）が残っている。直してレビューし直す")
    parked = {p.get("req") for p in s.get("parked") or []}
    for rid, n in sorted((s.get("streak") or {}).items()):
        if n < LADDER_REWORK or rid in parked:
            continue
        if len((s.get("reworks") or {}).get(rid, [])) < MAX_REWORKS:
            errors.append(f"{rid} は失敗が {n} 巡続いた。作り方を変える"
                          "（references/dead-end.md の 2。新しい ADR を書き、autopilot.py rework で記録する）")
        else:
            errors.append(f"{rid} は作り直しを {MAX_REWORKS} 回しても満たせない。autopilot.py block で人に戻す")
    return errors


def without_note(text):
    """末尾の 1 組の（…）を注記として除く（中の括弧は対にして数える。対にならなければ除かない）。"""
    if not text.endswith("）"):
        return text
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        depth += {"）": 1, "（": -1}.get(text[i], 0)
        if depth == 0:
            return text[:i]
    return text


def without_tail(text):
    """末尾の区切り（空白・、・,・。）と「 と」を、右から 1 回の走査で除く。"""
    i = len(text)
    while i:
        c = text[i - 1]
        if c.isspace() or c in "・、,。" or (c == "と" and i >= 2 and text[i - 2].isspace()):
            i -= 1
        else:
            break
    return text[:i]


def evidence_problem(root, evidence, seen=None):
    """pass の証拠の欄を EVIDENCE_* の文法で読み、テストが 1 つでも無ければ問題を返す。
    seen は 1 回の check の中で共有する、読んだファイル・見つけた名前・走査したバイト数。"""
    seen = seen if seen is not None else {"texts": {}, "found": set(), "scanned": 0}
    body = without_note(evidence.strip())
    m = EVIDENCE_FREE.search(body)
    tests, free = (body[:m.start()], body[m.start():]) if m else (body, "")
    if free and not free.split(":", 1)[1].strip():
        return "中身が空"
    tests, _, rest = tests.partition("。")  # 。の後ろは文（「。加えて cmd: ...」など）。テストを書き足すなら 。で切らない
    if "::" in rest:
        return EVIDENCE_FORMS
    tests = without_tail(tests)
    if not tests:
        return None if free else EVIDENCE_FORMS
    path = None
    for item in __import__("evidence").items(root, tests, EVIDENCE_SEP):
        p, sep, names = item.strip().strip("`").partition("::")
        path = p.strip() or path
        names = [n.strip() for n in names.split("::")]
        names[-1] = EVIDENCE_PARAM.sub("", names[-1])
        if not sep or not path or not all(names):
            return EVIDENCE_FORMS
        if path not in seen["texts"]:
            try:
                f = root / path
                data = read_capped(f, MAX_EVIDENCE_FILE) if f.is_file() else False
            except OSError as e:
                return f"{path} が読めない（{e.strerror or e}）"
            seen["texts"][path] = data if data in (None, False) else data.decode("utf-8", errors="replace")
        text = seen["texts"][path]
        if text is False:
            return f"{path} が無い"
        if text is None:
            return f"{path} が大きすぎる（{MAX_EVIDENCE_FILE:,} バイトまで）。テストのファイルでなければ cmd: で書く"
        for name in names:
            if (path, name) in seen["found"]:
                continue
            seen["scanned"] += len(text)
            if seen["scanned"] > MAX_EVIDENCE_SCAN:
                return f"証拠の名前を探す量が多すぎる（{MAX_EVIDENCE_SCAN:,} バイトまで）。並べるテストを減らす"
            if name not in text:
                return f"{path} に「{name}」が無い"
            seen["found"].add((path, name))
    return None


def spec_dirs(root):
    return [f.parent for f in sorted((root / "docs" / "specs").glob("*/state.json"))]


def active(root):
    found = []
    for d in spec_dirs(root):
        try:
            if load_state(d).get("phase") == "building":
                found.append(d)
        except (OSError, ValueError, AttributeError):
            continue
    return found


def report(errors, extra, ok_message):
    for e in errors:
        print(f"ERROR: {e}")
    for w in extra:
        print(f"NOTE: {w}")
    if not errors:
        print(ok_message)
    return 1 if errors else 0


def has_code(root):
    """docs/specs・docs/adr の外に、コードのファイルが 1 つでもあるか。

    git の中なら git が追っているファイルで、git の外（上のどこにも .git が無い）ならファイルシステムで決める。
    .git があるのに git が失敗したら、決められないので止める。
    """
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if out.returncode == 0:
        return any(not f.startswith((b"docs/specs/", b"docs/adr/")) for f in out.stdout.split(b"\0") if f)
    if any((p / ".git").exists() for p in (root, *root.parents)):
        sys.exit(f"git ls-files が失敗したので、既存の repo かを決められない: {out.stderr.decode(errors='replace').strip()}")
    for dirpath, dirs, files in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirs[:] = [d for d in dirs if (rel / d).as_posix() not in ("docs/specs", "docs/adr")]
        if files:
            return True
    return False


def cmd_init(a):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.slug):
        sys.exit("slug は英小文字・数字・ハイフンで書く")
    root = repo_root(Path.cwd())
    d = root / "docs" / "specs" / f"{datetime.date.today():%Y-%m-%d}-{a.slug}"
    if d.exists():
        sys.exit(f"{d} はもうある")
    existing = has_code(root)
    d.mkdir(parents=True)
    for name in ARTIFACTS:
        shutil.copy(TEMPLATES / name, d / name)
    s = {"phase": "discovery", "slug": a.slug, "created_at": time.time(), "existing": existing}
    if existing:
        out = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True, text=True)
        s["start"] = out.stdout.strip() if out.returncode == 0 else None  # 無ければ lint が大きさを数えられずに止める
    if s.get("start"):
        # spec を commit する慣行の無い repo（init の時点で docs/specs・docs/adr の下を 1 つも追っていない）では、その置き場を commit から外す
        tracked = git_lines(root, "ls-files", "--", "docs/specs/", "docs/adr/")
        uncommitted = [k for k in ("docs/specs/", "docs/adr/") if not any(f.startswith(k) for f in tracked)]
        if uncommitted:
            s["uncommitted"] = uncommitted
        keep_out_of_commits(root, uncommitted)
    save_state(d, s)
    exclude_check_scripts(root)
    if s.get("uncommitted"):
        print(f"NOTE: この repo は {'・'.join(s['uncommitted'])} の下を commit していない。{'・'.join(s['uncommitted'])} は "
              "commit しない（置き場に中身が `*` の .gitignore を書いた。git add -f もしない）。spec を commit しないときは要件の要約を、"
              "ADR を commit しないときは作り方の選択を、PR の本文に書く", file=sys.stderr)
    print(d)
    return 0


IGNORE_ALL = "*\n"


def keep_out_of_commits(root, uncommitted):
    """追っていない置き場には中身が `*` の .gitignore を書き（そのファイル自身も無視され、効くのはこの worktree だけ）、
    追い始めた置き場からは、前の init が書いたその .gitignore を消す。"""
    for k in ("docs/specs/", "docs/adr/"):
        p = root / k / ".gitignore"
        if k in uncommitted:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(IGNORE_ALL, encoding="utf-8")
        elif p.is_file() and p.read_text(encoding="utf-8") == IGNORE_ALL and not git_lines(root, "ls-files", "--", str(p.relative_to(root))):
            p.unlink()


def commit_note(s):
    """done の後に commit するものの知らせ。spec を commit しない repo では commit させない。"""
    if "docs/specs/" in (s.get("uncommitted") or []):
        return "spec・state.json・qa.md・tasks.md は commit しない（この repo は docs/specs を commit していない）"
    return "state.json を commit する"


def exclude_check_scripts(root):
    """評価役が直しの確かめのために残す .autopilot-qa/ を、git add -A が拾わないようにする（git の外では何もしない）。"""
    out = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=root, capture_output=True, text=True)
    if out.returncode != 0:
        return
    p = Path(out.stdout.strip())
    p = p if p.is_absolute() else root / p
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    if ".autopilot-qa/" not in lines:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join([*lines, ".autopilot-qa/"]) + "\n", encoding="utf-8")


def cmd_lint(a):
    errors, warnings = lint(Path(a.dir), preflight=True)
    return report(errors, warnings, "lint: OK")


def cmd_approve(a):
    d = Path(a.dir)
    import lineup
    errors, warnings = lineup.queue_lint(d) if a.queue else lint(d, at_approve=True)
    if not a.queue and lineup.after_name(d) and load_state(d).get("phase") == "discovery":
        errors.append("依る spec のある spec は --queue で承認する（着手のときに lineup.py next が依る spec の先端に載せ替える）")
    if errors:
        report(errors, warnings, "")
        return 1
    s = load_state(d)
    if s.get("phase") not in ("discovery", "blocked", "done"):
        sys.exit(f"approve は壁打ち中（discovery）・block の後・done の後だけ受ける（phase={s.get('phase')}）")
    adr = adr_error(d)
    if adr:
        sys.exit(f"{adr}。作り方の選択を ADR に書いてから承認する")
    since, what = (d / "spec.md").stat().st_mtime, "spec.md の最後の変更"
    if s.get("phase") == "blocked" and float((s.get("blocked") or {}).get("at", 0)) > since:
        since, what = float(s["blocked"]["at"]), "block"
    if s.get("phase") == "done":  # done の前の発言では戻さない。done の時刻が読めなければ戻さない
        done_at = s.get("done_at")
        if isinstance(done_at, bool) or not isinstance(done_at, (int, float)):
            sys.exit("done の時刻（state.json の done_at）が読めないので approve しない")
        if done_at > since:
            since, what = float(done_at), "done"
    session = require_user_after(d, since, what)
    if a.queue:
        return lineup.enqueue(d, s, a.by, session, warnings)
    budget = lineup.begin(d, s, a.by, s.get("phase"))
    take_over(d, session, "承認")
    save_state(d, s)
    report([], warnings + __import__("light").report(s), f"approved: 予算 {budget} 分。ここから自走する")
    return 0


def cmd_size(a):
    """評価役が観点 8 に使う大きさ（申告と、init の時点から tip までの差分で数えた大きさの大きい側）を出す。"""
    d = Path(a.dir)
    try:
        text = (d / "spec.md").read_text(encoding="utf-8")
        stated, size_err = stated_size(COMMENT_BLOCK.sub("", section(text, "制約") or ""))
        size, _, detail, errors = counted_size(d, COMMENT_BLOCK.sub("", section(text, "影響範囲") or ""), a.tip)
        if size_err or errors:
            raise RuntimeError(size_err or errors[0])
    except Exception as e:  # 数えられないときは大きい側に倒す
        print(f"ERROR: {e}。観点 8 の大きさ: L（数えられないので大きい側に倒す）")
        return 1
    print(f"{detail}。申告 {stated or 'なし'}。観点 8 の大きさ: {max(size, stated or 'S', key=SIZES.index)}")
    return 0


def cmd_check(a):
    errors, notes = check(Path(a.dir), a.stage)
    return report(errors, notes, "check: OK")


def cmd_done(a):
    d = Path(a.dir)
    errors, notes = check(d)
    if report(errors, notes, "check: OK"):
        return 1
    s = load_state(d)
    was_done = s.get("phase") == "done"
    s.update(phase="done", done_at=time.time())
    s["anomalies"] = done_anomalies(s)
    save_state(d, s)
    release(d)
    if not was_done:
        __import__("runlog").record(d, s, "done", s["done_at"])
    minutes = lambda since: round((s["done_at"] - since) / 60, 1)  # noqa: E731
    print(f"done: 承認から {minutes(s['approved_at'] + s.get('paused_sec', 0))} 分（確認待ちを除く）、着手から {minutes(s['created_at'])} 分。異常: {anomaly_line(s.get('anomalies') or {})}。{commit_note(s)}")
    text = (d / "spec.md").read_text(encoding="utf-8")
    stated, size_err = stated_size(COMMENT_BLOCK.sub("", section(text, "制約") or ""))
    size, detail = None, "数えていない"
    if size_err:  # 読めない大きさの行は大きい側に倒す（cmd_size と同じ向き）
        stated, detail = "L", size_err
    if s.get("existing"):
        try:
            size, _, detail, _ = counted_size(d, COMMENT_BLOCK.sub("", section(text, "影響範囲") or ""))
        except RuntimeError as e:
            print(f"NOTE: 大きさを数えられない（{e}）。PR の大きさは差分を見て決める")
    if "L" in (stated, size):  # 合意し直しと自走中に育った L も、PR を作る前のここで受け持つ
        print(f"NOTE: {SPLIT_PR}（申告 {stated or 'なし'}・{detail}）")
    overnight = __import__("overnight")
    print("\n".join(overnight.report(d) + [f"NOTE: {x}" for x in __import__("light").report(s)]))
    overnight.notify(d)
    return 0


def cmd_block(a):
    d = Path(a.dir)
    reqs = requirements((d / "spec.md").read_text(encoding="utf-8"))
    if a.req not in reqs:
        sys.exit(f"{a.req} は spec.md の要件に無い")
    if not a.reason.strip() or not a.evidence.strip():
        sys.exit("--reason と --evidence は空にできない")
    s = load_state(d)
    if s.get("phase") not in ("building", "wait"):
        refuse(s, "block は自走中（building）か確認待ち（wait）だけ受ける")
    gate = __import__("overnight").production_errors(d, s, done=False)
    if gate and not (a.no_rollback or "").strip():
        sys.exit(f"本番が良くない: {gate[0]}。戻してから block するか、戻せない理由を --no-rollback で書く（朝の報告の先頭に出る）")
    wait_at = float(s["wait"]["at"]) if s.get("phase") == "wait" and s.get("wait") else None
    s.update(phase="blocked", blocked={"req": a.req, "reason": a.reason, "evidence": a.evidence, "at": time.time(),
                                       **({"no_rollback": a.no_rollback} if gate else {})})
    save_state(d, s)
    release(d)
    __import__("runlog").record(d, s, "block", s["blocked"]["at"], top_end=wait_at or s["blocked"]["at"])
    print(f"blocked: {a.req}。人に 1 通で示す")
    __import__("overnight").notify(d)
    return 0


def cmd_wait(a):
    d = Path(a.dir)
    if not a.reason.strip():
        sys.exit("--reason は空にできない")
    s = load_state(d)
    if s.get("phase") != "building":
        refuse(s, "wait は自走中（building）だけ受ける")
    gate = __import__("overnight").production_errors(d, s, done=False)
    if gate:
        sys.exit(f"本番が良くないまま wait にしない: {gate[0]}")
    s.update(phase="wait", wait={"reason": a.reason, "at": time.time()})
    save_state(d, s)
    print("wait: 確認を人に 1 通で示す。返事を受けたら resume で戻る")
    return 0


def cmd_resume(a):
    d = Path(a.dir)
    s = load_state(d)
    if s.get("phase") != "wait":
        refuse(s, "resume は wait の後だけ受ける")
    session = require_user_after(d, float(s["wait"]["at"]), "wait")
    s.setdefault("history", []).append({"phase": "wait", **s["wait"]})
    s.update(phase="building", wait=None, paused_sec=s.get("paused_sec", 0) + time.time() - float(s["wait"]["at"]))
    take_over(d, session, "再開")
    save_state(d, s)
    print("resume: 自走に戻る")
    return 0


def cmd_adopt(a):
    """自走中・確認待ちの spec を、このセッション（CLAUDE_CODE_SESSION_ID）が引き継ぐ。以後は Stop hook が止める。"""
    d = Path(a.dir)
    s = load_state(d)
    if s.get("phase") not in ("building", "wait", "queued"):
        refuse(s, "adopt は自走中（building）・確認待ち（wait）・着手待ち（queued）だけ受ける")
    take_over(d, os.environ.get("CLAUDE_CODE_SESSION_ID"), "引き継ぎ")
    pause_since_last_activity(d)  # 前のセッションが止まってから今までを予算から外す（開き直したときと同じ）
    print("adopt: このセッションが引き継いだ。" + ("確認待ちなので、人の返事を受けてから resume で戻る" if s.get("phase") == "wait" else "/autopilot の C の手順で続ける"))
    return 0


def status(d):
    """再開のときに読む状態（phase・予算・梯子・残り・続け方）を行で返す。読めなければ例外を投げる。"""
    s = load_state(d)
    phase = s.get("phase")
    lines = [f"{d}: phase={phase}"]
    if phase == "building":
        import overnight
        elapsed, budget, label = overnight.budget_view(d, s)
        lines.append(f"{label} {elapsed:.0f} 分 / 予算 {budget:.0f} 分（確認待ち・機械の待ちを除く）")
        if overnight.await_record(d):
            lines.append(f"機械の待ち: {d / overnight.AWAIT_FILE} がある。待ちのプロセスが死んでいれば、overnight.py await を起動し直す")
        for rid, n in sorted((s.get("streak") or {}).items()):
            if n:
                lines.append(f"{rid}: {n} 巡続いた失敗（references/dead-end.md の段に従う）")
        for rid, adrs in sorted((s.get("reworks") or {}).items()):
            if adrs:
                lines.append(f"{rid}: 作り直し {len(adrs)} 回（{', '.join(adrs)}）")
        errors, _ = check(d)
        lines += [f"残り: {e}" for e in errors] or ["残り: なし。autopilot.py done を実行する"]
        lines.append("続け方: /autopilot の C の手順を、上の残りを消す段から人に聞かずに続ける")
    elif phase == "wait":
        lines.append(f"確認待ち: {(s.get('wait') or {}).get('reason')}。人の返事を受けてから autopilot.py resume {d}")
    elif phase == "queued":
        lines.append("承認済みで着手待ち: lineup.py next で承認した順に着手する（人の発言は要らない）")
    elif phase == "blocked":
        b = s.get("blocked") or {}
        lines.append(f"人に戻した: {b.get('req')}（{b.get('reason')}）。返事を受けたら /autopilot の「人に戻るとき」の手順に従う")
    elif phase == "discovery":
        lines.append("壁打ち中: /autopilot の A・B の手順で spec を詰める")
    elif phase == "done":
        lines.append(f"完了。{AFTER_DONE.replace('<dir>', str(d))}")
    else:
        lines.append("完了")
    return lines


def cmd_status(a):
    print("\n".join(status(Path(a.dir))))
    return 0


def pause_since_last_activity(d):
    """自走中の spec の、最後の活動から今までを確認待ちと同じく予算から外す（中断の後の再開のとき）。"""
    s = load_state(d)
    if s.get("phase") != "building":
        return
    last = float(s.get("last_active_at") or s["approved_at"])
    s["paused_sec"] = float(s.get("paused_sec", 0)) + max(0.0, time.time() - last)
    save_state(d, s)


def cmd_active(a):
    for d in active(repo_root(Path.cwd())):
        print(d)
    return 0


AFTER_DONE = ("done の後は Stop hook が止めないので、確認は wait を使わずにそのまま人に聞く。"
              "人に直しを頼まれたら、spec を直さずに済むなら tasks.md に直しのタスクを足して "
              "autopilot.py approve <dir> --by <返事の要約> で自走に戻る（spec を直すなら /autopilot の「done の後に直しを頼まれたとき」の手順に従う）")


def refuse(s, what):
    """受けない phase のときに止める。done なら、done の後の道（approve で戻る・そのまま聞く）を示す。"""
    if s.get("phase") == "done":
        sys.exit(f"{what}（phase=done）。{AFTER_DONE}")
    sys.exit(f"{what}（phase={s.get('phase')}）")


def building_state(d):
    s = load_state(d)
    if s.get("phase") != "building":
        refuse(s, "自走中（building）だけ受ける")
    return s, requirements((d / "spec.md").read_text(encoding="utf-8"))


def add_fail(s, rid, source, evidence):
    """失敗を記録する。数えるのは次のレビューの巡（1 つの巡で何件あっても 1 回）。"""
    s.setdefault("fails", {}).setdefault(rid, []).append({"from": source, "evidence": evidence, "at": time.time()})
    return f"{rid}: 失敗を記録した。次のレビューの巡で 1 回として数える"


def ladder_message(rid, n):
    if n >= LADDER_REWORK:
        return f"{rid}: 失敗が {n} 巡続いた。作り方を変える（references/dead-end.md の 2）"
    if n >= LADDER_INVESTIGATE:
        return f"{rid}: 失敗が {n} 巡続いた。推測で直さず原因を調べる（references/dead-end.md の 1）"
    return f"{rid}: 失敗が {n} 巡続いた"


def cmd_fail(a):
    d = Path(a.dir)
    s, reqs = building_state(d)
    if a.req not in reqs:
        sys.exit(f"{a.req} は spec.md の要件に無い")
    if a.source not in FAIL_SOURCES:
        sys.exit(f"--from は {' / '.join(FAIL_SOURCES)} のどれか")
    if not a.evidence.strip():
        sys.exit("--evidence は空にできない")
    msg = add_fail(s, a.req, a.source, a.evidence)
    if a.source == "impl":  # 実装役が満たせなかったら、次のレビューを待たずに段を上げて作り直す（上げた段を渡すたびに 1 段）
        reviews = s.get("reviews") or []
        msg += "\n" + (raise_impl(d, s, a.req, "実装役の失敗", reviews[-1]["at"] if reviews else float(s.get("approved_at", 0)))
                       or f"{a.req}: 上げた段をまだ渡していないので、段はそのまま")
    save_state(d, s)
    print(msg)
    return 0


def raise_impl(d, s, rid, reason, since, at=None):
    """その要件の実装役の段を 1 段上げて記録し、文を返す。since（巡の始め）か、その要件を最後に渡した dispatch の
    遅い方の後にもう上げていれば上げずに None（上げた段をまだ渡していない）。渡し直すたびに 1 段上がる。
    review の巡で上げるときの at はその巡の記録の時刻（次の巡の since と、上げた後のレビューの数えを揃える）。"""
    import ladder
    raises = s.setdefault("raises", [])
    since = max([since] + [float(x["at"]) for x in s.get("dispatches") or [] if rid in (x.get("reqs") or [])])
    if any(r.get("role") == "impl" and r.get("req") == rid and float(r["at"]) > since for r in raises):
        return None
    sec = section((d / "spec.md").read_text(encoding="utf-8"), "モデル")
    before = ladder.impl_agent(sec, raises, [rid])[0]
    if before is None:
        return None  # もう一番上を超えている
    raises.append({"role": "impl", "req": rid, "reason": reason, "at": at or time.time()})
    after = ladder.impl_agent(sec, raises, [rid])[0]
    raises[-1].update({"from": before, "to": after or "park"})
    return (f"{rid}: 実装役の段を上げた: {before}→{after}（{reason}）" if after else
            f"{rid}: 一番上の段（{before}）でも通らない。その要件を park に積む（overnight.py park <dir> --kind other --req {rid} ...）")


def cmd_review(a):
    d = Path(a.dir)
    s, reqs = building_state(d)
    high = [] if a.high.strip() == "none" else [r.strip() for r in a.high.split(",") if r.strip()]
    if a.high.strip() != "none" and not high:
        sys.exit("--high は none か、high を受けた要件の番号（R1,R2）")
    unknown = [r for r in high if r not in reqs]
    if unknown:
        sys.exit(f"{', '.join(unknown)} は spec.md の要件に無い。high は要件の番号に結び付ける")
    import overnight
    gate, tip = overnight.review_gate(d, s)
    if gate:
        sys.exit(gate)
    reviews = s.setdefault("reviews", [])
    since = reviews[-1]["at"] if reviews else float(s.get("approved_at", 0))
    for rid in high:
        add_fail(s, rid, "review", "最後のレビューの high")
    reviews.append({"high": high, "at": time.time(), "sha": tip})
    streak, msgs = s.setdefault("streak", {}), []
    import ladder
    for rid in reqs:  # 巡ごとに数える: この巡に high か失敗があれば +1、無ければ 0（3 巡に届いた要件は作り直すまで戻さない）
        new = [f for f in (s.get("fails") or {}).get(rid, []) if float(f["at"]) > since]
        if new:
            streak[rid] = streak.get(rid, 0) + 1
            msgs.append(ladder_message(rid, streak[rid]))
            reason = ladder.raise_reason(streak[rid], LADDER_INVESTIGATE, LADDER_REWORK)
            line = reason and raise_impl(d, s, rid, reason, since, reviews[-1]["at"])  # この要件について 1 巡に 1 段、上げた段を渡した後ならもう 1 段（main は何も呼ばない）
            if line:
                msgs.append(line)
        elif streak.get(rid, 0) < LADDER_REWORK:
            streak[rid] = 0
    save_state(d, s)
    print("\n".join(msgs) if msgs else "review: high なし")
    return 0


def cmd_rework(a):
    d = Path(a.dir)
    s, reqs = building_state(d)
    if a.req not in reqs:
        sys.exit(f"{a.req} は spec.md の要件に無い")
    if (s.get("streak") or {}).get(a.req, 0) < LADDER_REWORK:
        sys.exit(f"{a.req} の失敗は {LADDER_REWORK} 巡続いていない。作り直しの前に直すか原因を調べる")
    reworks = s.setdefault("reworks", {})
    if len(reworks.get(a.req, [])) >= MAX_REWORKS:
        sys.exit(f"{a.req} は作り直しを {MAX_REWORKS} 回した。autopilot.py block {d} --req {a.req} で人に戻す")
    root = repo_root(d).resolve()
    head = (d / "spec.md").read_text(encoding="utf-8").split("\n## ", 1)[0]
    used = {(root / m.group(1)).resolve() for m in ADR_LINE.finditer(head)}
    used |= {(root / p).resolve() for ps in reworks.values() for p in ps}
    adr = (root / a.adr).resolve()  # 別名（./・絶対パス・..）を同じ ADR として比べる
    if adr in used:
        sys.exit(f"{a.adr} は前に使った ADR。作り方の変更は新しい ADR に書く")
    if not adr.is_file() or root not in adr.parents:
        sys.exit(f"ADR {a.adr} が repo の中に無い")
    __import__("rootcause").refuse_if_unfit(adr.read_text(encoding="utf-8"), a.adr, d, reqs)
    reworks.setdefault(a.req, []).append(str(adr.relative_to(root)))
    s.setdefault("streak", {})[a.req] = 0
    save_state(d, s)
    print(f"rework: {a.req} の {len(reworks[a.req])} 回目の作り直し。spec の作り方の節と tasks.md を直して進む（tasks.md の `  - メモ: 前提:` の行は消さない）")
    return 0


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


def session_transcript():
    """このセッション（CLAUDE_CODE_SESSION_ID）の transcript の場所。UserPromptSubmit hook が人の発言ごとに記録する。無ければ None。"""
    f = prompt_file(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    try:
        p = json.loads(f.read_text(encoding="utf-8")).get("transcript_path") if f else None
    except (OSError, ValueError, AttributeError):
        return None
    return p if isinstance(p, str) and p else None


def done_anomalies(s):
    """done が出す件数。Stop hook の記録と、done の時点までの transcript の数え直しの、型ごとの大きいほう。"""
    counts = dict(s.get("anomalies") or {})
    path = session_transcript()
    try:
        now = anomalies(path, since=float(s["approved_at"])) if path else None
    except (OSError, ValueError, KeyError, TypeError):
        now = None
    for k, v in (now or {}).items():
        counts[k] = max(v, counts.get(k, 0))
    return counts


def cmd_anomalies(a):
    for p in a.paths:
        try:
            c = anomalies(p)
        except OSError as e:
            print(f"{p}: 読めない（{type(e).__name__}）")
            continue
        print(f"{p}: 承認なし" if c is None else f"{p}: " + "、".join(f"{k} {v}" for k, v in c.items()))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="autopilot.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("slug")
    for name in ("lint", "done", "status"):
        sub.add_parser(name).add_argument("dir")
    cp = sub.add_parser("check")
    cp.add_argument("dir")
    cp.add_argument("--stage", choices=("all", "pr"), default="all")  # pr: PR を作る前（範囲の完了条件を見ない）
    ap = sub.add_parser("approve")
    ap.add_argument("dir")
    ap.add_argument("--by", required=True)
    ap.add_argument("--queue", action="store_true")  # 承認だけして着手は lineup.py next に回す
    bp = sub.add_parser("block")
    bp.add_argument("dir")
    for flag in ("--req", "--reason", "--evidence"):
        bp.add_argument(flag, required=True)
    bp.add_argument("--no-rollback")
    wp = sub.add_parser("wait")
    wp.add_argument("dir")
    wp.add_argument("--reason", required=True)
    sub.add_parser("resume").add_argument("dir")
    sub.add_parser("adopt").add_argument("dir")
    fp = sub.add_parser("fail")
    fp.add_argument("dir")
    fp.add_argument("--req", required=True)
    fp.add_argument("--from", dest="source", required=True)
    fp.add_argument("--evidence", required=True)
    rp = sub.add_parser("review")
    rp.add_argument("dir")
    rp.add_argument("--high", required=True)
    kp = sub.add_parser("rework")
    kp.add_argument("dir")
    kp.add_argument("--req", required=True)
    kp.add_argument("--adr", required=True)
    zp = sub.add_parser("size")
    zp.add_argument("dir")
    zp.add_argument("--tip")
    sub.add_parser("active")
    sub.add_parser("anomalies").add_argument("paths", nargs="+")
    a = p.parse_args(argv)
    return globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    sys.exit(main())
