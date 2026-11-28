"""軽量フローの判定（保護 path とデプロイ・ロールバックのコマンドの許可リスト）。stages・deploy のほかに scripts を import しない下の層。
light.py（approve の入口）と autopilot.py の check が呼ぶ。"""
import os
import re
import subprocess
from pathlib import Path

import deploy
from stages import COMMENT_BLOCK, classify, repo_root, section

# pattern の当て方は pathspecs() の docstring を見る
DEFAULT_PROTECTED = ("*.tf", "*.tf.json", "*.tfvars", "*.tfvars.json", "*.tfstate", "*.tfstate.*", ".terraform", "*.tofu", "*.tofu.json", "*.hcl", "terraform", "infra",
                     "*guardrails*", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md", ".claude", ".mcp.json", ".github",
                     ".spec-autopilot")
CONFIG = Path(".spec-autopilot") / "protected-paths"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def config_lines(text):
    return [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith("#")]


def git(root, *args):
    """NUL 区切りで読む。pathspec の magic を環境変数で切られないようにし、失敗したら例外を投げる（止める側に倒す）。"""
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "0", "GIT_GLOB_PATHSPECS": "0", "GIT_NOGLOB_PATHSPECS": "0", "GIT_ICASE_PATHSPECS": "0", "LC_ALL": "C"}
    out = subprocess.run(["git", "-c", "core.quotePath=false", args[0], "-z", *args[1:]], cwd=root, capture_output=True, text=True, env=env)
    if out.returncode:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} が {out.returncode} で終わった")
    return [f for f in out.stdout.split("\0") if f]


def patterns(root, base):
    """既定と、起点（base）の commit の設定。設定を PR の中で変えると、`.spec-autopilot` 自体が既定の保護なので止まる。"""
    extra = ""
    entries = {} if base == EMPTY_TREE else dict(  # 「無い」は木の一覧で決める
        reversed(e.split("\t", 1)) for e in git(root, "ls-tree", base, "--", CONFIG.parent.as_posix(), CONFIG.as_posix()))
    want = {CONFIG.parent.as_posix(): ("040000",), CONFIG.as_posix(): ("100644", "100755")}  # symlink などは中身を読めないので止める
    bad = [f"{k}（{v.split()[0]}）" for k, v in entries.items() if k in want and v.split()[0] not in want[k]]
    if bad:
        raise RuntimeError(f"起点の設定が普通のファイルでない: {', '.join(bad)}")
    if CONFIG.as_posix() in entries:
        out = subprocess.run(["git", "cat-file", "blob", f"{base}:{CONFIG.as_posix()}"], cwd=root, capture_output=True)
        if out.returncode:  # 木にあって読めない（blob が手元に無いなど）ときは、足した pattern を落とさずに止める
            raise RuntimeError(out.stderr.decode(errors="replace").strip() or "起点の設定を読めない")
        extra = out.stdout.decode("utf-8").removeprefix("\ufeff")  # UTF-8 でなければ ValueError で止まる。先頭の BOM は外す
        bad = [i for i, x in enumerate(extra.splitlines(), 1) if not x.isprintable()]
        if bad:  # 見えない文字（ゼロ幅空白など）が入った pattern は黙って当たらなくなるので止める
            raise RuntimeError(f"起点の設定の {', '.join(map(str, bad))} 行目に表示できない文字がある")
    return list(dict.fromkeys([*DEFAULT_PROTECTED, *config_lines(extra)]))


def pathspecs(pats, within=None):
    """pattern を git の glob pathspec にする。前後の `/` を外し、`/` を含まない行はどの深さにも、含む行は repo の root から当て、
    どちらも配下に当てる。大文字と小文字は区別しない（止める側）。within を渡すと、`/` を含まない行だけを、その下の深さに当てる。"""
    out = []
    for p in pats:
        core = p.strip("/")
        if not core or (within and "/" in core):
            continue
        if "/" not in core:
            core = f"{within}/**/{core}" if within else "**/" + core
        out += [f":(glob,icase){core}", f":(glob,icase){core}/**"]
    return out


def changed(root, base, specs):
    """起点から、PR に入りうる変更（HEAD・index・作業ツリーの差と、追っていないファイル）のうち specs に当たる path。"""
    specs = ["--", *specs]
    # rename は両側の名前を出し、submodule の無視の設定（.gitmodules・diff.ignoreSubmodules）に gitlink の変更を隠させない
    diff = ("diff", "--name-only", "--no-renames", "--ignore-submodules=none")
    files = set(git(root, *diff, base, *specs)) | set(git(root, *diff, "--cached", base, *specs))
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root, capture_output=True).returncode == 0:
        files |= set(git(root, *diff, base, "HEAD", *specs))
    # 追っていないファイルも、後で commit すれば PR に入るので数える（git が無視するものは --exclude-standard で外れる）
    return files | set(git(root, "ls-files", "--others", "--exclude-standard", *specs))


def hits(d, s):
    """起点から PR に入りうる変更で触れた保護 path。spec 自身の置き場は、置き場の名前では当てず、置き場の下の深さにだけ
    `/` を含まない pattern を当てる。git が無視するファイル・途中の commit で触れて戻したものは数えない（限界）。照合は git がする。"""
    root = repo_root(d)
    base = s.get("light_base") or EMPTY_TREE
    own = Path(d).resolve().relative_to(Path(root).resolve()).as_posix()
    pats = patterns(root, base)
    return sorted(changed(root, base, [*pathspecs(pats), f":(exclude){own}"]) | changed(root, base, pathspecs(pats, own)))


KEYS = ("デプロイの起動", "ロールバック")


def command_errors(text, after_approve=False):
    """軽量フローの spec のデプロイ・ロールバックを許可リストで確かめる。合意ありでは承認のときに人がこの 2 行を見るが、
    軽量フローでは誰も見ない（block の後の返事も spec の全体を見たものではない）ので、agent の書いたコマンドを打たせない。
    - `## 自走の範囲` の見出し（この綴りのまま。コードブロックやコメントの中も数える）は 1 つだけで、コメントを外した後、`- <キー>: <値>` の行と空行だけ。`デプロイの起動` は「マージで自動」か「なし（マージした commit で QA）」か空、`ロールバック` は revert の PR か空
    - spec のほかの所（散文・綴りの違う見出しの節・閉じたコメント）に書いたコマンドは機械では拾わない。軽量フローの run では after-pr.md の 3・5 が
      「起動のコマンドとコマンドでの戻しは無い」と agent に言う（LLM の指示なので、守れているかは機械で確かめられない。限界）"""
    way = ("`autopilot.py block` で記録して人に戻る" if after_approve else
           "マージで自動に動く workflow か revert の PR にする（デプロイの workflow が無ければ起動を「なし（マージした commit で QA）」、"
           "範囲がマージまで・PR までなら空でよい）か、合意ありで spec を作り直す")
    out = []
    raw = section(text, deploy.SCOPE_SECTION) or ""
    body = COMMENT_BLOCK.sub("", raw)
    _, bad = classify(body, [("row", deploy.SCOPE_ROW)])
    if raw.count("<!--") != raw.count("-->"):  # 閉じていないコメントが、後ろのコメントの閉じまでを隠さないように
        bad.append("<!-- と --> の数が合わない")
    if bad:
        out.append(f"軽量フローでは `## {deploy.SCOPE_SECTION}` に `- <キー>: <値>` の行のほかを書けない（{bad[0][:40]}）。{way}")
    n = len(re.findall(rf"^## {re.escape(deploy.SCOPE_SECTION)}\s*$", text, re.M))  # 読み手は最初の節だけを見る（コードブロックの中も数える）
    if n > 1:
        out.append(f"軽量フローでは `## {deploy.SCOPE_SECTION}` の節を 1 つにまとめる（{n} 個ある）。{way}")
    rows = deploy.scope_rows(text) or {}
    allowed = {"デプロイの起動": (deploy.AUTO_DEPLOY, deploy.NO_DEPLOY), "ロールバック": (deploy.REVERT,)}
    found = {k for k in KEYS if (rows.get(k) or "") not in ("", *allowed[k])}
    return out + [f"軽量フローでは `- {key}:` は「{'」か「'.join(allowed[key])}」か空だけにする"
                  f"（人が見ないままコマンドを打つことになる）。{way}" for key in KEYS if key in found]


def errors(d, s):
    """軽量フローの run の check の ERROR。合意ありの run では []。"""
    if not s.get("light"):
        return []
    out = command_errors((Path(d) / "spec.md").read_text(encoding="utf-8"), after_approve=True)
    try:
        found = hits(d, s)
    except (RuntimeError, OSError, ValueError) as e:  # 数えられないときは止める側に倒す
        return out + [f"保護された path を確かめられない（{e}）"]
    if found:
        out.append(f"保護された path に触れた: {', '.join(found)}。軽量フローでは進めない。"
                   "`autopilot.py block` で記録して人に戻る（spec の全体を人に示す。合意ありで進めるなら spec を作り直す）")
    return out
