"""spec の「## 制約」の `- playbook:` の lint。名前は references/playbooks/ のファイル一覧で閉じる（コードに名前を並べない）。"""
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "references" / "playbooks"
LINE = re.compile(r"^- playbook:(.*)$", re.M)
NAME = re.compile(r"[a-z][a-z0-9-]*")
NONE = re.compile(r"なし（[^）\S]*[^）\s][^）]*）")
HOW = "`- playbook: <名前>[、<名前>]`（名前は references/playbooks/ のファイル名。当たらないなら `- playbook: なし（<理由>）`）"


def lint(constraints):
    """「## 制約」の本文（コメントを除いたもの）から ERROR の一覧を返す。"""
    rows = LINE.findall(constraints)
    if not rows:
        return [f"「## 制約」に {HOW} を書く"]
    if len(rows) > 1:
        return [f"`- playbook:` の行が {len(rows)} 本ある。1 行に {HOW} の形でまとめる"]
    value = rows[0].strip()
    if NONE.fullmatch(value):
        return []
    known = {p.stem for p in DIR.glob("*.md")}
    names = [n.strip() for n in value.split("、")]
    errors = [f"`- playbook:` の「{n or value}」が読めない。{HOW}" for n in names if not NAME.fullmatch(n)]
    errors += [f"`- playbook:` の {n} が無い（ある名前: {'・'.join(sorted(known))}）" for n in names
               if NAME.fullmatch(n) and n not in known]
    errors += [f"`- playbook:` に {n} が 2 回ある" for n in sorted({n for n in names if names.count(n) > 1})]
    return errors
