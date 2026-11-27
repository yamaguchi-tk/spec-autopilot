"""autopilot.py goal <親> が、作業ツリーで done でない子を、子のブランチの done の state と gh で確かめたマージから done と読むこと。
子の done の state は子のブランチにだけ commit し、main の作業ツリーは building のまま。gh は PATH に置いた偽物で答える。"""
import json
import os
import subprocess
import sys

import pytest

from test_autopilot import PLUGIN, run, state, repo  # noqa: F401
from test_goal_child import child_spec, parent_goal
from test_goal_done import set_phase

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(" ".join(args) + "\n")
ans = json.load(open(os.path.join(d, "script.json"))).get(" ".join(args[:3]) if args[:2] == ["pr", "view"] else " ".join(args[:2]))
if ans is None:
    sys.stderr.write("fake gh: no answer\n")
    sys.exit(1)
out = ans.get("out", "")
sys.stdout.write(out if isinstance(out, str) else json.dumps(out))
sys.exit(ans.get("code", 0))
'''

sys.path.insert(0, str(PLUGIN / "scripts"))
import merged_child  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


@pytest.fixture
def gh(tmp_path, monkeypatch):
    d = tmp_path / "fakegh"
    d.mkdir()
    exe = d / "gh"
    exe.write_text(FAKE_GH, encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_DIR", str(d))

    class G:
        def __init__(self):
            self.script = {"repo view": {"out": {"defaultBranchRef": {"name": "main"}}}}
            self.save()

        def save(self):
            (d / "script.json").write_text(json.dumps(self.script), encoding="utf-8")

        def pr(self, n, **over):
            """マージ済みで、全部の条件がそろった PR の答え。over で 1 つ崩す。"""
            self.script[f"pr view {n}"] = {"out": {**good_pr(n), **over}}
            self.save()

        def raw(self, n, code=0, out=""):
            self.script[f"pr view {n}"] = {"code": code, "out": out}
            self.save()

        def calls(self):
            f = d / "calls.log"
            return f.read_text().splitlines() if f.exists() else []
    return G()


def sha_of(n):
    return f"{n:040x}"


def good_pr(n, child="x"):
    return {"state": "MERGED", "mergedAt": "2026-11-28T00:00:00Z", "mergeCommit": {"oid": sha_of(n)},
            "baseRefName": "main", "headRefName": f"branch-{n}", "files": [{"path": f"docs/specs/{child}/state.json"}]}


def git(repo, *args):
    r = subprocess.run([*GIT, *args], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def done_on_branch(repo, d, branch, merges):
    """main の作業ツリーの子は building のまま。子のブランチにだけ、done と merges を commit する。"""
    git(repo, "checkout", "-q", "-b", branch)
    s = state(d)
    s.update(phase="done", merges=merges)
    (d / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    git(repo, "commit", "-qam", "done")
    git(repo, "checkout", "-q", "main")


def merge_rec(n, **over):
    return {"pr": n, "at": 1.0, "sha": sha_of(n), "head": "h", **over}


def family(repo, gh, n_children=2, branches=None):
    """親と子 n 本（子 i が R<i+1> を受け持ち、PR 番号は 10+i）。子はどれも main では building。"""
    parent = parent_goal(repo)
    ds = [child_spec(repo, parent, slug=f"c{i}", reqs="R1、R2" if n_children == 1 else f"R{i + 1}") for i in range(n_children)]
    for d in ds:
        set_phase(d, "building")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    for i, d in enumerate(ds):
        done_on_branch(repo, d, (branches or {}).get(i, f"branch-{10 + i}"), [merge_rec(10 + i)])
        gh.script[f"pr view {10 + i}"] = {"out": {**good_pr(10 + i, d.name), "headRefName": (branches or {}).get(i, f"branch-{10 + i}")}}
    gh.save()
    return parent, ds


def set_pr(gh, d, i, **over):
    gh.script[f"pr view {10 + i}"]["out"].update(over)
    gh.save()


def refused(repo, parent, child):
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and "ERROR" in r.stdout, r.stdout + r.stderr
    assert child.name in r.stdout and "building" in r.stdout
    assert state(parent)["phase"] == "discovery"
    assert state(child)["phase"] == "building"


def test_goal_reads_children_done_on_their_branches_from_merged_prs_and_names_branch_and_pr(repo, gh):
    parent, (a, b) = family(repo, gh)
    r = run(repo, "goal", str(parent))
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(parent)["phase"] == "done"
    la = next(x for x in r.stdout.splitlines() if x.startswith("R1"))
    lb = next(x for x in r.stdout.splitlines() if x.startswith("R2"))
    assert a.name in la and "branch-10" in la and "10" in la
    assert b.name in lb and "branch-11" in lb and "11" in lb
    assert state(a)["phase"] == "building" and state(b)["phase"] == "building"  # 作業ツリーの子は書き換えない


def test_goal_reads_a_remote_tracking_ref_with_the_remote_name_removed_from_the_head_branch(repo, gh):
    parent, (a,) = family(repo, gh, 1, branches={0: "claude/child-x"})
    git(repo, "update-ref", "refs/remotes/origin/claude/child-x", "refs/heads/claude/child-x")
    git(repo, "branch", "-q", "-D", "claude/child-x")
    r = run(repo, "goal", str(parent))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claude/child-x" in r.stdout


def test_goal_does_not_read_a_child_whose_pr_is_not_merged(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_pr(gh, b, 1, state="OPEN", mergedAt=None)
    refused(repo, parent, b)


def test_goal_does_not_read_a_child_whose_merge_commit_differs_from_the_record(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_pr(gh, b, 1, mergeCommit={"oid": sha_of(999)})
    refused(repo, parent, b)


def test_goal_does_not_read_a_child_when_the_pr_changed_no_file_under_the_child_directory(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_pr(gh, b, 1, files=[{"path": "docs/specs/other/state.json"}, {"path": f"docs/specs/{b.name}-x/state.json"}])
    refused(repo, parent, b)


def test_goal_does_not_read_a_child_whose_pr_base_is_not_the_default_branch(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_pr(gh, b, 1, baseRefName="stacked")
    refused(repo, parent, b)


def test_goal_does_not_read_a_child_whose_pr_head_differs_from_the_branch_read(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_pr(gh, b, 1, headRefName="another-branch")
    refused(repo, parent, b)


@pytest.mark.parametrize("pr", ["11", True, 0, -3, 1.5, "--web", "https://github.com/o/r/pull/11", None])
def test_goal_does_not_pass_a_pr_number_that_is_not_a_positive_integer_to_gh(repo, gh, pr):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "checkout", "-q", "branch-10")
    s = state(a)
    s["merges"] = [merge_rec(10, pr=pr)]
    (a / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    git(repo, "commit", "-qam", "bad pr")
    git(repo, "checkout", "-q", "main")
    refused(repo, parent, a)
    assert not any(c.startswith("pr view") for c in gh.calls())


def test_goal_does_not_read_a_child_whose_last_merge_record_is_a_rollback(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "checkout", "-q", "branch-10")
    s = state(a)
    s["merges"] = [merge_rec(10), merge_rec(12, rollback=True, reason="戻す")]
    (a / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    git(repo, "commit", "-qam", "rollback")
    git(repo, "checkout", "-q", "main")
    gh.script["pr view 12"] = {"out": {**good_pr(12, a.name), "headRefName": "branch-10"}}
    gh.save()
    refused(repo, parent, a)


def test_goal_reads_the_last_merge_record_not_an_earlier_one(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "checkout", "-q", "branch-10")
    s = state(a)
    s["merges"] = [merge_rec(9), merge_rec(10)]
    (a / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    git(repo, "commit", "-qam", "two merges")
    git(repo, "checkout", "-q", "main")
    assert run(repo, "goal", str(parent)).returncode == 0
    assert "pr view 9" not in gh.calls() and "pr view 10 --json state,mergedAt,mergeCommit,baseRefName,headRefName,files" in gh.calls()


def test_goal_does_not_read_a_branch_state_that_is_not_done_or_has_no_merge_record(repo, gh):
    parent, (a, b) = family(repo, gh)
    git(repo, "checkout", "-q", "branch-11")
    s = state(b)
    s["merges"] = []
    (b / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    git(repo, "commit", "-qam", "no merges")
    git(repo, "checkout", "-q", "main")
    refused(repo, parent, b)


@pytest.mark.parametrize("answer", [{"code": 1, "out": ""}, {"code": 0, "out": "not json"}, {"code": 0, "out": "[]"}, {"code": 0, "out": {"state": "MERGED"}}])
def test_goal_falls_back_to_the_working_tree_phase_when_gh_fails_or_answers_something_unreadable(repo, gh, answer):
    parent, (a, b) = family(repo, gh)
    gh.script["pr view 11"] = answer
    gh.save()
    refused(repo, parent, b)


def test_goal_falls_back_when_the_default_branch_cannot_be_read(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    gh.script["repo view"] = {"code": 1}
    gh.save()
    refused(repo, parent, a)


def test_goal_asks_gh_nothing_for_a_child_already_done_in_the_working_tree(repo, gh):
    parent, (a, b) = family(repo, gh)
    set_phase(a, "done")
    set_phase(b, "done")
    assert run(repo, "goal", str(parent)).returncode == 0
    assert gh.calls() == []


# --- gh の失敗を stderr に 1 行出す（T2）---

def failure_lines(text):
    return [x for x in text.splitlines() if "gh" in x and "確かめられない" in x]


@pytest.mark.parametrize("answer, kind", [
    ({"code": 4, "out": ""}, "exit 4"),
    ({"code": 0, "out": "not json"}, "JSON でない"),
    ({"code": 0, "out": "[]"}, "JSON でない"),
])
def test_goal_names_the_child_the_pr_and_the_kind_on_stderr_when_gh_fails_and_still_falls_back(repo, gh, answer, kind):
    parent, (a, b) = family(repo, gh)
    gh.script["pr view 11"] = answer
    gh.save()
    refused(repo, parent, b)
    r = run(repo, "goal", str(parent))
    lines = failure_lines(r.stderr)
    assert len(lines) == 1 and b.name in lines[0] and "11" in lines[0] and kind in lines[0], r.stderr
    assert a.name not in r.stderr


def test_goal_names_the_pr_on_stderr_when_the_default_branch_cannot_be_read(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    gh.script["repo view"] = {"code": 1}
    gh.save()
    refused(repo, parent, a)
    lines = failure_lines(run(repo, "goal", str(parent)).stderr)
    assert len(lines) == 1 and a.name in lines[0] and "10" in lines[0] and "exit 1" in lines[0]


def test_goal_prints_nothing_on_stderr_when_gh_answers_and_every_child_is_read(repo, gh):
    parent, (a, b) = family(repo, gh)
    r = run(repo, "goal", str(parent))
    assert r.returncode == 0 and r.stderr == ""


def test_goal_prints_nothing_on_stderr_when_git_show_finds_no_state_file_in_any_ref(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "branch", "-q", "-D", "branch-10")
    r = run(repo, "goal", str(parent))
    assert r.returncode == 1 and r.stderr == "" and "pr view 10" not in " ".join(gh.calls())


def test_goal_prints_one_line_for_a_failing_pr_found_on_two_refs(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "update-ref", "refs/remotes/origin/branch-10", "refs/heads/branch-10")
    gh.script["pr view 10"] = {"code": 4, "out": ""}
    gh.save()
    assert len(failure_lines(run(repo, "goal", str(parent)).stderr)) == 1


def test_goal_asks_gh_for_the_default_branch_once_when_the_child_state_is_on_two_refs(repo, gh):
    parent, (a,) = family(repo, gh, 1)
    git(repo, "update-ref", "refs/remotes/origin/other", "refs/heads/branch-10")
    set_pr(gh, a, 0, headRefName="zzz")  # どの ref でも head が合わず、既定のブランチまでは引く
    refused(repo, parent, a)
    assert gh.calls().count("repo view --json defaultBranchRef") == 1


@pytest.mark.parametrize("raised, kind", [
    (subprocess.TimeoutExpired(["gh"], 60), "タイムアウト"),
    (FileNotFoundError(2, "No such file", "gh"), "起動できない"),
])
def test_read_returns_none_and_names_the_child_pr_and_kind_when_gh_times_out_or_cannot_start(repo, gh, capsys, monkeypatch, raised, kind):
    parent, (a,) = family(repo, gh, 1)
    real = subprocess.run

    def fake(args, *rest, **kw):
        if args[0] == "gh":
            raise raised
        return real(args, *rest, **kw)
    monkeypatch.setattr(merged_child.subprocess, "run", fake)
    assert merged_child.read(repo, a) is None
    lines = failure_lines(capsys.readouterr().err)
    assert len(lines) == 1 and a.name in lines[0] and "10" in lines[0] and kind in lines[0], lines
