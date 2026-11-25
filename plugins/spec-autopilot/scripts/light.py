#!/usr/bin/env python3
"""人との spec 合意を省く軽量フロー。

  light.py approve <dir> --source <Issue の URL か依頼文の要約>   人の返事を待たずに自走を始める（phase=building、light=true）

- 入れるのは、受入条件が Issue に書いてあるか、依頼文だけで要件・範囲・完了が決まるときだけ（commands/autopilot.md の L）
- 自走の上限は PR 作成まで。`- 範囲:` が「PR まで」でなければ approve しない。マージ・デプロイ・QA の書き込み・ロールバックの記録
  （overnight.py ready・merged・qa・rolled-back）を受けない。範囲をマージ以降に広げる根拠は人が承認した spec なので、合意を省いた run には及ばない
- 止まる条件は、保護された path（下の既定と、repo の `.spec-autopilot/protected-paths`）に触れたとき。init の時点の commit から
  HEAD・index・作業ツリーまでの変更ファイル、途中の commit で触れたファイル、追っていないファイルの path で機械的に決める。
  git が無視するファイルは PR に入らないので見ない（手元の設定の書き換えは防がない。限界）。承認の前から当たっているなら approve しない。spec.md が承認の後に変わったとき（範囲が広がる）は、合意ありと同じく check が止める
- 印は block・done の後の approve でも外さない（その返事は spec の全体を見たものではない）。合意ありで進めるなら spec を作り直す

範囲: 軽量フローの承認・保護 path の判定・PR 作成までの上限（ready・merged・qa・rolled-back の拒否）だけを足す。合意ありの run の挙動は変えない
想定する脅威: 事故（agent が範囲を広げる・保護 path に触れる・マージに進む）。敵対的な agent が state.json を書き換えて印を消すことは防がない
やらないこと: 影響範囲の宣言と差分の突き合わせ、hook での編集・`gh pr merge` の拒否、利用する repo の設定の形の検査、git が無視するファイル（PR に入らない手元のファイル）の判定
"""
import argparse
import fnmatch
import os
import posixpath
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402

# `/` を含まない pattern は path のどの要素にも当て、含む pattern は path かその上のディレクトリに当てる（fnmatch の * は / にも当たる）
DEFAULT_PROTECTED = ("*.tf", "*.tf.json", "*.tfvars", "*.tfvars.json", "*.tfstate", "*.tfstate.*", ".terraform", "*.tofu", "*.tofu.json", "*.hcl", "terraform", "infra",
                     "*guardrails*", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md", ".claude", ".mcp.json", ".github",
                     ".spec-autopilot")
CONFIG = Path(".spec-autopilot") / "protected-paths"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CEILING = "軽量フロー（人と spec を合意していない run）の自走の上限は PR 作成まで。マージ・デプロイ・QA の書き込みはしない（人の指示を待つ）"


def config_lines(text):
    pats = (x.strip().strip("/") for x in text.splitlines() if x.strip() and not x.strip().startswith("#"))
    return [p[3:] if p.startswith("**/") else p for p in pats if p]


def patterns(root, base, recorded=()):
    """既定と、承認のときに控えた pattern・起点（base）の版・今の版の和。承認の後に設定を緩めても、守る path は減らない。"""
    f = Path(root) / CONFIG
    old = subprocess.run(["git", "show", f"{base}:{CONFIG.as_posix()}"], cwd=root, capture_output=True, text=True)
    extra = config_lines(f.read_text(encoding="utf-8") if f.is_file() else "") + config_lines(old.stdout if old.returncode == 0 else "")
    return list(dict.fromkeys([*DEFAULT_PROTECTED, *recorded, *extra]))


def protected(path, pats, fold=False):
    """`/` を含まない pattern は path のどの要素にも、含む pattern は path かその前置（ディレクトリ）のどれかに当てる。
    fold は大文字と小文字を区別しない repo（core.ignorecase）で、両方を casefold して比べる。"""
    if fold:
        path, pats = path.casefold(), [p.casefold() for p in pats]
    parts = path.split("/")
    prefixes = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    return any(any(fnmatch.fnmatchcase(x, p) for x in (prefixes if "/" in p else parts)) for p in pats)


def ignorecase(root):
    r = subprocess.run(["git", "config", "--bool", "core.ignorecase"], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() == "true"


def own_adr(root, base, text):
    """保護から外す spec の ADR。`docs/adr/` の下で、symlink でなく、起点に無い（この run で作った）ものだけ。"""
    m = ap.ADR_LINE.search(text)
    if not m:
        return None
    path = posixpath.normpath(m.group(1))
    full = Path(root) / path
    exact = {p.casefold() for p in DEFAULT_PROTECTED if "*" not in p}  # 規則ファイルの名前（docs/adr/CLAUDE.md など）は外さない
    if not path.startswith("docs/adr/") or full.is_symlink() or posixpath.basename(path).casefold() in exact:
        return None
    new = subprocess.run(["git", "cat-file", "-e", f"{base}:{path}"], cwd=root, capture_output=True).returncode != 0
    return path if new else None


def commits_touched(root, base):
    """起点から HEAD までの各 commit（merge を含む）で触れた path。利用者の設定（署名の表示など）に左右されない plumbing で読む。"""
    revs = subprocess.run(["git", "rev-list", "HEAD" if base == EMPTY_TREE else f"{base}..HEAD"], cwd=root, capture_output=True, text=True)
    if revs.returncode:
        raise RuntimeError(revs.stderr.strip() or "git rev-list が失敗した")
    out = subprocess.run(["git", "-c", "core.quotePath=false", "diff-tree", "--stdin", "-r", "-m", "--root", "--no-commit-id",
                          "--name-only", "--no-renames", "-z"], cwd=root, input=revs.stdout, capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr.strip() or "git diff-tree が失敗した")
    return {f for f in out.stdout.split("\0") if f}


def hits(d, s):
    """起点から触れた保護 path。追っているものは起点と HEAD・index・作業ツリーの差と、途中の commit で触れたもの、
    追っていない（無視されていない）ものは作った時期によらず数える。git が無視するファイルは PR に入らないので見ない（限界）。"""
    root = ap.repo_root(d)
    base = s.get("light_base") or EMPTY_TREE
    pats = patterns(root, base, s.get("light_patterns") or ())
    skip = Path(d).resolve().relative_to(Path(root).resolve()).as_posix() + "/"
    own = own_adr(root, base, (d / "spec.md").read_text(encoding="utf-8"))
    fold = ignorecase(root)
    # rename は両側の名前を出し（--no-renames）、非 ASCII の名前は引用しない（git_lines の -z と quotePath=false）
    diff = ("diff", "--name-only", "--no-renames")
    files = set(ap.git_lines(root, *diff, base)) | set(ap.git_lines(root, *diff, "--cached", base))
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root, capture_output=True).returncode == 0:
        files |= set(ap.git_lines(root, *diff, base, "HEAD"))
        files |= commits_touched(root, base)
    files |= set(ap.git_lines(root, "ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if not f.startswith(skip) and f != own and protected(f, pats, fold))


def errors(d, s):
    """軽量フローの run の check の ERROR。合意ありの run では []。"""
    if not s.get("light"):
        return []
    import overnight

    out = []
    scope = (overnight.scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("範囲")
    if scope != overnight.PR:
        out.append(f"{CEILING}。`- 範囲:` は「{overnight.PR}」にする（今は「{scope}」）")
    try:
        found = hits(d, s)
    except (RuntimeError, OSError, ValueError) as e:  # 数えられないときは止める側に倒す
        return out + [f"保護された path を確かめられない（{e}）"]
    if found:
        out.append(f"保護された path に触れた: {', '.join(found)}。軽量フローでは進めない。"
                   "`autopilot.py block` で記録して人に戻る（spec の全体を人に示す。合意ありで進めるなら spec を作り直す）")
    return out


def refuse(s, what):
    """overnight.py の ready・merged・qa・rolled-back が、軽量フローの run で呼ばれたら止める。"""
    if s.get("light"):
        print(f"ERROR: {CEILING}。{what}は受けない")
        sys.exit(1)


def report(s):
    return [CEILING] if s.get("light") else []


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
    if lineup.after_name(d):
        errs.append("依る spec のある spec は軽量フローで始めない（合意ありで --queue で承認する）")
    text = (d / "spec.md").read_text(encoding="utf-8")
    if ap.stated_size(ap.COMMENT_BLOCK.sub("", ap.section(text, "制約") or ""))[0] != "S":
        errs.append("軽量フローは `- 大きさ: S` の spec だけで始める（予算も人が見ないので、小さい修正に限る）")
    if errs:
        ap.report(errs, warnings, "")
        return 1
    root = ap.repo_root(d)
    base = s.get("start") or EMPTY_TREE  # init の時点（S の試作の commit も判定に入れる）。新しく作る repo は空の木から
    try:
        pats = patterns(root, base)
        before = hits(d, {"light_base": base, "light_patterns": pats})
    except (RuntimeError, OSError, ValueError) as e:
        sys.exit(f"保護された path を確かめられない（{e}）ので承認しない")
    if before:  # init より後の commit か、追っていないファイルが、もう保護 path に当たっている
        sys.exit(f"保護された path に承認の前から当たっている: {', '.join(before)}。軽量フローでは始めない（合意ありで進めるか、人が片づける）")
    budget = lineup.begin(d, s, f"軽量フロー（人の承認なし）: {a.source.strip()}", "discovery")
    s.update(light=True, light_base=base, light_patterns=pats)
    ap.take_over(d, os.environ.get("CLAUDE_CODE_SESSION_ID"), "軽量フローの承認")
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
