"""セッションごとの、自走させる spec の記録の読み書き。SESSION_ID のほかに scripts を import しない下の層。"""
import json
import os
from pathlib import Path

from stages import SESSION_ID


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
