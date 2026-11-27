#!/usr/bin/env python3
"""子の spec が、子のブランチの done の state と、gh で確かめたマージから done と読めるか（goal の cover が当てる）。

子の done の state はマージの後に子のブランチへ commit され、main の作業ツリーの state.json は done でない。
ブランチの state は agent が書けるので、PR の記録で次の 7 つが全部確かめられたときだけ (ブランチ, PR の番号) を返す:
記録の PR の番号が正の整数・記録が戻しでない・PR が MERGED で mergedAt がある・マージの commit が記録と同じ・
base が repo の既定のブランチ・head のブランチ名が state を読んだブランチと同じ・PR が子のディレクトリの下のファイルを変えた。
git・gh の失敗・読めない・例外は「確かめられない」で None（呼び出し側は作業ツリーの phase で読む）。
"""
import json
import subprocess
from pathlib import PurePosixPath


def run(args, cwd):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} {args[1]} が失敗（exit {r.returncode}）")
    return r.stdout


def gh_json(root, *args):
    return json.loads(run(["gh", *args], root))


def branch_name(ref):
    """`refs/heads/x` は x、`refs/remotes/<remote>/x` は remote の名前を除いた x。remote の HEAD は None。"""
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    parts = ref.split("/", 3)
    return parts[3] if ref.startswith("refs/remotes/") and len(parts) == 4 and parts[3] != "HEAD" else None


def last_merge(text):
    """ブランチの state.json の中身から、done で merges の最後に pr と sha がある記録。無ければ None。"""
    s = json.loads(text)
    merges = s.get("phase") == "done" and s.get("merges")
    last = merges[-1] if isinstance(merges, list) and merges else None
    return last if isinstance(last, dict) and isinstance(last.get("sha"), str) and last["sha"] else None


def positive_int(x):
    return isinstance(x, int) and not isinstance(x, bool) and x > 0


def merged_ok(root, rel, branch, rec):
    """記録 rec の PR が、7 つの条件を満たすか。PR の番号と rollback は gh を呼ぶ前に見る。"""
    if not positive_int(rec.get("pr")) or rec.get("rollback"):
        return False
    v = gh_json(root, "pr", "view", str(rec["pr"]), "--json", "state,mergedAt,mergeCommit,baseRefName,headRefName,files")
    if v.get("state") != "MERGED" or not v.get("mergedAt"):
        return False
    if not isinstance(v.get("mergeCommit"), dict) or v["mergeCommit"].get("oid") != rec["sha"]:
        return False
    default = gh_json(root, "repo", "view", "--json", "defaultBranchRef")["defaultBranchRef"]["name"]
    if not default or v.get("baseRefName") != default or v.get("headRefName") != branch:
        return False
    return any(isinstance(f, dict) and isinstance(f.get("path"), str) and PurePosixPath(f["path"]).is_relative_to(rel)
               for f in v.get("files") or [])


def read(root, child):
    """子のディレクトリ child の (done を読んだブランチ, PR の番号)。確かめられなければ None。"""
    try:
        rel = PurePosixPath(child.resolve().relative_to(root.resolve()).as_posix())
        refs = run(["git", "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"], root).split()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return None
    for ref in refs:
        branch = branch_name(ref)
        if branch is None:
            continue
        try:
            rec = last_merge(run(["git", "show", f"{ref}:{rel}/state.json"], root))
            if rec and merged_ok(root, rel, branch, rec):
                return branch, rec["pr"]
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
            continue
    return None
