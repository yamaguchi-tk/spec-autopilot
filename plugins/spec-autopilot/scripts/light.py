#!/usr/bin/env python3
"""人との spec 合意を省く軽量フロー。

  light.py approve <dir> --source <Issue の URL か依頼文の要約>   人の返事を待たずに自走を始める（phase=building、light=true）

- 入れるのは、受入条件が Issue に書いてあるか、依頼文だけで要件・範囲・完了が決まるときだけ（commands/autopilot.md の L）
- 自走の上限は PR 作成まで。`- 範囲:` が「PR まで」でなければ approve しない。マージ・デプロイ・QA の書き込みの記録
  （overnight.py ready・merged・qa）を受けない。範囲をマージ以降に広げる根拠は人が承認した spec なので、合意を省いた run には及ばない
- 止まる条件は、保護された path（下の既定と、repo の `.spec-autopilot/protected-paths`）に触れたとき。承認の時点の HEAD から
  作業ツリーまでの変更ファイルの path で機械的に決める。spec.md が承認の後に変わったとき（範囲が広がる）は、合意ありと同じく check が止める
- 人が `autopilot.py approve` で承認し直したら、合意ありの run になる（lineup.begin が印を外す）

範囲: 軽量フローの承認・保護 path の判定・PR 作成までの上限（ready・merged・qa の拒否）だけを足す。合意ありの run の挙動は変えない
想定する脅威: 事故（agent が範囲を広げる・保護 path に触れる・マージに進む）。敵対的な agent が state.json を書き換えて印を消すことは防がない
やらないこと: 影響範囲の宣言と差分の突き合わせ、hook での編集の拒否、利用する repo の設定の形の検査
"""
import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402

# `/` を含まない pattern は path のどの要素にも当て、含む pattern は path 全体に当てる（fnmatch の * は / にも当たる）
DEFAULT_PROTECTED = ("*.tf", "*.tfvars", "terraform", "infra", "*guardrails*", "CLAUDE.md", "AGENTS.md", ".claude")
CONFIG = Path(".spec-autopilot") / "protected-paths"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CEILING = "軽量フロー（人と spec を合意していない run）の自走の上限は PR 作成まで。マージ・デプロイ・QA の書き込みはしない（人の指示を待つ）"


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return [x for x in r.stdout.splitlines() if x]


def patterns(root):
    f = Path(root) / CONFIG
    extra = f.read_text(encoding="utf-8").splitlines() if f.is_file() else []
    return [*DEFAULT_PROTECTED, *(x.strip() for x in extra if x.strip() and not x.strip().startswith("#"))]


def protected(path, pats):
    return any(fnmatch.fnmatchcase(path, p) if "/" in p else any(fnmatch.fnmatchcase(c, p) for c in path.split("/"))
               for p in pats)


def touched(root, base):
    """承認の時点（base）から作業ツリーまでに変わったファイル（commit していないもの・追っていないものを含む）。"""
    return sorted(set(git(root, "diff", "--name-only", base)) | set(git(root, "ls-files", "--others", "--exclude-standard")))


def errors(d, s):
    """軽量フローの run の check の ERROR。合意ありの run では []。"""
    if not s.get("light"):
        return []
    import overnight

    out = []
    scope = (overnight.scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("範囲")
    if scope != overnight.PR:
        out.append(f"{CEILING}。`- 範囲:` は「{overnight.PR}」にする（今は「{scope}」）")
    root = ap.repo_root(d)
    try:
        hits = [f for f in touched(root, s.get("light_base") or EMPTY_TREE) if protected(f, patterns(root))]
    except RuntimeError as e:  # 数えられないときは止める側に倒す
        return out + [f"保護された path を確かめられない（{e}）"]
    if hits:
        out.append(f"保護された path に触れた: {', '.join(hits)}。軽量フローでは進めない。"
                   "`autopilot.py block` で記録して人に戻る（人が承認し直せば合意ありの run として続けられる）")
    return out


def refuse(s, what):
    """overnight.py の ready・merged・qa が、軽量フローの run で呼ばれたら止める。"""
    if s.get("light"):
        print(f"ERROR: {CEILING}。{what}は受けない")
        sys.exit(1)


def report(s):
    return [f"NOTE: {CEILING}"] if s.get("light") else []


def cmd_approve(a):
    d = Path(a.dir)
    import lineup
    import overnight

    s = ap.load_state(d)
    if s.get("phase") != "discovery":
        sys.exit(f"軽量フローの approve は壁打ち中（discovery）だけ受ける（phase={s.get('phase')}）")
    if not a.source.strip():
        sys.exit("--source（Issue の URL か依頼文の要約）は空にできない")
    errs, warnings = ap.lint(d, at_approve=True)
    scope = (overnight.scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("範囲")
    if scope != overnight.PR:
        errs.append(f"{CEILING}。`- 範囲:` を「{overnight.PR}」にする（今は「{scope}」）")
    adr = ap.adr_error(d)
    if adr:
        errs.append(adr)
    if errs:
        ap.report(errs, warnings, "")
        return 1
    root = ap.repo_root(d)
    try:
        base = git(root, "rev-parse", "HEAD")[0]
    except RuntimeError:
        base = EMPTY_TREE  # commit が 1 つも無い repo
    budget = lineup.begin(d, s, f"軽量フロー（人の承認なし）: {a.source.strip()}", "discovery")
    s.update(light=True, light_base=base)
    ap.take_over(d, __import__("os").environ.get("CLAUDE_CODE_SESSION_ID"), "軽量フローの承認")
    ap.save_state(d, s)
    ap.report([], warnings, f"approved（軽量フロー）: 予算 {budget} 分。{CEILING}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="light.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("approve")
    x.add_argument("dir")
    x.add_argument("--source", required=True)
    a = p.parse_args(argv)
    return cmd_approve(a)


if __name__ == "__main__":
    sys.exit(main())
