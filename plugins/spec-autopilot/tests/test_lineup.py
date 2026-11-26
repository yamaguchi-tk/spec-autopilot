"""複数の spec をまとめて承認し（approve --queue）、夜の間に 1 本ずつ着手する（lineup.py next）流れを、
入口（autopilot.py・lineup.py の CLI、Stop hook、SessionStart hook）から通して確かめる。"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_autopilot import (EXISTING_SECTIONS, GOOD_SPEC, PLUGIN, existing_repo, init_spec, repo, run, state, stop_hook,  # noqa: F401
                           user_says)
from test_overnight import FULL, GIT, gh, scoped  # noqa: F401
from test_rollback import NIGHT_NOTES, aws_home, fake_mac, gdd_on, with_budget

LINEUP = PLUGIN / "scripts" / "lineup.py"
START = PLUGIN / "hooks" / "session_start.py"


def line(repo, *args, session="s1"):
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": session}
    return subprocess.run([sys.executable, str(LINEUP), *args], cwd=repo, capture_output=True, text=True, env=env,
                          timeout=60)


def spec(repo, slug, after=None, size="S", text=GOOD_SPEC):
    d = init_spec(repo, slug)
    rows = f"- 大きさ: {size}" + (f"\n- 依る spec: {after.name}" if after else "")
    (d / "spec.md").write_text(text.replace("- 大きさ: S", rows), encoding="utf-8")
    return d


def queue(repo, *dirs):
    user_says(repo)
    for d in dirs:
        r = run(repo, "approve", str(d), "--by", "OK", "--queue")
        assert r.returncode == 0, r.stdout + r.stderr


def record(session="s1"):
    f = Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "sessions" / f"{session}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def set_phase(d, **kv):
    s = state(d)
    s.update(kv)
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")


# --- まとめて承認する ---

def test_one_utterance_queues_several_specs_without_starting_the_clock(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    for d in (a, b):
        s = state(d)
        assert s["phase"] == "queued" and "approved_at" not in s and s["spec_sha256"] and s["approved_by"] == "OK"
    assert record() == [str(a.resolve()), str(b.resolve())]


def test_queue_still_needs_an_utterance_after_the_last_change_of_the_spec(repo):
    a = spec(repo, "a")
    user_says(repo)
    time.sleep(0.01)
    (a / "spec.md").write_text((a / "spec.md").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    r = run(repo, "approve", str(a), "--by", "OK", "--queue")
    assert r.returncode == 1 and state(a)["phase"] == "discovery"


def test_queue_refuses_a_dependency_that_this_session_has_not_approved(repo):
    other = spec(repo, "other")
    b = spec(repo, "b", after=other, size="M")
    user_says(repo)
    r = run(repo, "approve", str(b), "--by", "OK", "--queue")
    assert r.returncode == 1 and other.name in r.stdout + r.stderr and state(b)["phase"] == "discovery"


def test_queue_refuses_a_small_spec_that_depends_on_another(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="S")
    user_says(repo)
    r = run(repo, "approve", str(b), "--by", "OK", "--queue")
    assert r.returncode == 1 and "M 以上" in r.stdout and state(b)["phase"] == "discovery"


def test_queue_measures_the_sso_session_with_the_budgets_queued_before(repo, tmp_path, monkeypatch):
    aws_home(tmp_path, monkeypatch, 100)  # 1 本は 30 分 + マージ後 30 分で入るが、2 本目は 120 分で入らない
    text = scoped(FULL, **{"AWS の profile": "dev"})
    a, b = spec(repo, "a", text=text), spec(repo, "b", text=text)
    user_says(repo)
    assert run(repo, "approve", str(a), "--by", "OK", "--queue").returncode == 0
    r = run(repo, "approve", str(b), "--by", "OK", "--queue")
    assert r.returncode == 1 and "aws sso login" in r.stdout and state(b)["phase"] == "discovery"


def night_notes_of_the_second(repo, tmp_path, monkeypatch, first, second):
    """1 本目を first 分（マージ後の予算なし → 見込みは 2 倍）、2 本目を second 分でまとめて承認し、2 本目の承認の出力を返す。"""
    fake_mac(tmp_path, monkeypatch, batt="Now drawing from 'Battery Power'", autoinstall="1", awake="0")
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    a = spec(repo, "a", text=with_budget(scoped(FULL), first))
    b = spec(repo, "b", text=with_budget(scoped(FULL), second))
    user_says(repo)
    assert run(repo, "approve", str(a), "--by", "OK", "--queue").returncode == 0
    r = run(repo, "approve", str(b), "--by", "OK", "--queue")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_queue_gives_no_night_notes_when_the_specs_queued_before_and_this_one_total_an_hour(repo, tmp_path, monkeypatch):
    out = night_notes_of_the_second(repo, tmp_path, monkeypatch, 10, 20)  # 前に 10＋10 分、この spec は 20＋20 分
    assert not [w for w in NIGHT_NOTES if w in out], out


def test_queue_gives_the_night_notes_when_the_specs_queued_before_push_the_end_past_an_hour(repo, tmp_path, monkeypatch):
    out = night_notes_of_the_second(repo, tmp_path, monkeypatch, 20, 20)  # 前に 20＋20 分、この spec は 20＋20 分で 80 分
    assert all(w in out for w in NIGHT_NOTES), out


# --- 着手（next） ---

def test_next_starts_the_first_queued_spec_without_an_utterance(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    before = time.time()
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "building" and state(a)["approved_at"] >= before and state(a)["budget_min"] == 30
    assert state(b)["phase"] == "queued"
    assert run(repo, "status", str(a)).stdout.count("予算") == 1


def test_next_refuses_while_a_spec_is_building(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    assert line(repo, "next").returncode == 0
    r = line(repo, "next")
    assert r.returncode == 1 and a.name in r.stdout + r.stderr and state(b)["phase"] == "queued"


def test_next_blocks_a_spec_changed_after_the_approval_and_starts_the_following_one(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    (a / "spec.md").write_text((a / "spec.md").read_text(encoding="utf-8").replace("Enter", "Space"), encoding="utf-8")
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "blocked" and "変わった" in state(a)["blocked"]["reason"]
    assert state(b)["phase"] == "building"
    assert str(a.resolve()) not in record()


def test_next_blocks_a_spec_whose_check_at_the_start_fails(repo):
    a = spec(repo, "a")
    queue(repo, a)
    gdd_on(repo)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "gdd-dev.local.md").write_text("---\nactive: true\n---\n", encoding="utf-8")
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "blocked" and "GDD" in state(a)["blocked"]["reason"]


def test_next_blocks_the_spec_that_depends_on_a_blocked_spec(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="blocked", blocked={"req": "R1", "reason": "x", "evidence": "y", "at": time.time()})
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and a.name in state(b)["blocked"]["reason"]


def test_next_passes_over_a_spec_whose_dependency_is_waiting_for_a_person(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    c = spec(repo, "c")
    queue(repo, b, c)
    set_phase(a, phase="wait", wait={"reason": "確認", "at": time.time()})
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "queued" and state(c)["phase"] == "building"


def test_next_starts_a_dependent_spec_on_top_of_its_dependency(repo, tmp_path):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    b = spec(wb, "b", after=a, size="M")
    queue(wb, b)
    assert line(repo, "next").returncode == 0
    (repo / "core.js").write_text("// a\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "core.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "impl a"], cwd=repo, check=True)
    tip = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    set_phase(a, phase="done", done_at=time.time())
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "building" and state(b)["start"] == tip
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, "HEAD"], cwd=wb).returncode == 0


def test_next_blocks_a_dependent_spec_that_cannot_be_put_on_its_dependency(repo, tmp_path):
    note = Path("docs") / "adr" / "note.md"  # docs の下だけを追う repo（既存の repo の検査に入らない）
    (repo / note).parent.mkdir(parents=True)
    (repo / note).write_text("0\n", encoding="utf-8")
    subprocess.run([*GIT, "add", str(note)], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    b = spec(wb, "b", after=a, size="M")
    queue(wb, b)
    (wb / note).write_text("dirty\n", encoding="utf-8")  # 追っているファイルの、commit していない変更
    (repo / note).write_text("a\n", encoding="utf-8")
    subprocess.run([*GIT, "commit", "-q", "-am", "impl a"], cwd=repo, check=True)
    set_phase(a, phase="done", done_at=time.time())
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and "載せ" in state(b)["blocked"]["reason"]


# --- 依る spec の lint（承認の前は書式だけ、着手で突き合わせる） ---

LATER = "- 変える: `src/lines.js:1`（`countLines`）\n"  # 前の spec が作るファイル（init の時点に無い）


def dependent(repo, impact=LATER, size="- 大きさ: M", premise=None):
    existing_repo(repo)
    a = spec(repo, "a", size="M", text=GOOD_SPEC + EXISTING_SECTIONS)
    d = init_spec(repo, "b")
    text = GOOD_SPEC.replace("- 大きさ: S", f"{size}\n- 依る spec: {a.name}") + EXISTING_SECTIONS.replace(
        "- 変える: `src/board.js:12`（`clearLines`）\n", impact)
    if premise:
        text = text.replace("- 前提: なし（新しく作るので、頼る既存の振る舞いが無い）", premise)
    (d / "spec.md").write_text(text, encoding="utf-8")
    return a, d


def test_lint_of_a_dependent_spec_does_not_match_paths_against_the_init_commit(repo):
    _, b = dependent(repo)
    r = run(repo, "lint", str(b))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("kw, word", [
    ({"impact": "- 変える src/lines.js\n"}, "影響範囲の行の形"),
    ({"size": ""}, "大きさ"),
    ({"premise": "- 前提: 盤面は消える\n  - 見た: なにか"}, "前提の行の形"),
])
def test_a_dependent_spec_is_not_queued_with_a_broken_format(repo, kw, word):
    a, b = dependent(repo, **kw)
    queue(repo, a)
    r = run(repo, "approve", str(b), "--by", "OK", "--queue")
    assert r.returncode == 1 and word in r.stdout, r.stdout
    assert state(b)["phase"] == "discovery"


def test_a_dependent_spec_with_a_good_format_is_queued(repo):
    a, b = dependent(repo)
    queue(repo, a, b)
    assert state(b)["phase"] == "queued"


def test_a_dependent_spec_is_approved_only_into_the_queue(repo):
    a, b = dependent(repo)
    queue(repo, a)
    r = run(repo, "approve", str(b), "--by", "OK")
    assert r.returncode == 1 and "--queue" in r.stdout + r.stderr and state(b)["phase"] == "discovery"


def test_next_starts_a_dependent_spec_on_the_head_of_a_dependency_waiting_for_review(repo, tmp_path, gh):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    b = spec(wb, "b", after=a, size="M")
    queue(wb, b)
    assert line(repo, "next").returncode == 0
    (repo / "core.js").write_text("// a\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "core.js"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "impl a"], cwd=repo, check=True)
    tip = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    gh.answers("pr view", [{"out": {"reviewDecision": "REVIEW_REQUIRED", "headRefOid": tip}}] * 2)
    assert line(repo, "hold", str(a), "--pr", "7").returncode == 0
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "wait" and state(b)["phase"] == "building" and state(b)["start"] == tip
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, "HEAD"], cwd=wb).returncode == 0


# --- レビュー待ち ---

def building_with_pr(repo, gh, decision="REVIEW_REQUIRED"):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    assert line(repo, "next").returncode == 0
    gh.answers("pr view", [{"out": {"reviewDecision": decision, "headRefOid": "h1"}}])
    r = line(repo, "hold", str(a), "--pr", "7")
    assert r.returncode == 0, r.stdout + r.stderr
    return a, b


def test_hold_sets_a_review_wait_aside_and_next_starts_the_following_spec(repo, gh):
    a, b = building_with_pr(repo, gh)
    w = state(a)["wait"]
    assert state(a)["phase"] == "wait" and w["kind"] == "review" and w["pr"] == 7 and w["head"] == "h1"
    assert line(repo, "next").returncode == 0
    assert state(b)["phase"] == "building" and state(a)["phase"] == "wait"


def test_next_takes_an_approved_review_back_before_the_following_spec(repo, gh):
    a, b = building_with_pr(repo, gh)
    gh.answers("pr view", [{"out": {"reviewDecision": "APPROVED", "headRefOid": "h1"}}])
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "building" and state(b)["phase"] == "queued"


def test_next_does_not_take_back_a_review_approved_on_another_head(repo, gh):
    a, b = building_with_pr(repo, gh)
    gh.answers("pr view", [{"out": {"reviewDecision": "APPROVED", "headRefOid": "h2"}}])
    assert line(repo, "next").returncode == 0
    assert state(a)["phase"] == "wait" and state(b)["phase"] == "building"


def test_next_takes_the_review_wait_back_when_nothing_is_queued(repo, gh):
    a, b = building_with_pr(repo, gh)
    set_phase(b, phase="done", done_at=time.time())
    gh.answers("pr view", [{"out": {"reviewDecision": "REVIEW_REQUIRED", "headRefOid": "h1"}}])
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(a)["phase"] == "building" and "await" in r.stdout


# --- Stop hook ---

def decision(repo):
    r = stop_hook(repo)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def test_stop_hook_demands_next_while_queued_specs_remain(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    out = decision(repo)
    assert out.get("decision") == "block" and "lineup.py next" in out["reason"]
    set_phase(a, phase="done", done_at=time.time())
    out = decision(repo)
    assert out.get("decision") == "block" and "lineup.py next" in out["reason"]


def test_stop_hook_demands_a_block_for_a_spec_past_twice_its_budget_while_specs_are_queued(repo):
    a, b = spec(repo, "a"), spec(repo, "b")
    queue(repo, a, b)
    assert line(repo, "next").returncode == 0
    set_phase(a, approved_at=time.time() - 3 * 30 * 60)
    out = decision(repo)
    assert out.get("decision") == "block" and "block" in out["reason"] and "lineup.py next" in out["reason"]


def test_stop_hook_lets_a_person_wait_alone_go(repo):
    a = spec(repo, "a")
    queue(repo, a)
    assert line(repo, "next").returncode == 0
    set_phase(a, phase="wait", wait={"reason": "確認", "at": time.time()})
    assert decision(repo).get("decision") != "block"


def test_stop_hook_demands_next_for_a_review_wait_left_alone(repo, gh):
    a, b = building_with_pr(repo, gh)
    set_phase(b, phase="done", done_at=time.time())
    out = decision(repo)
    assert out.get("decision") == "block" and "lineup.py next" in out["reason"]


# --- 再開 ---

def test_session_start_and_status_show_a_queued_spec(repo):
    a = spec(repo, "a")
    queue(repo, a)
    r = subprocess.run([sys.executable, str(START)], input=json.dumps({"cwd": str(repo), "session_id": "s1", "source": "compact"}),
                       capture_output=True, text=True, cwd=repo)
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert a.name in ctx and "lineup.py next" in ctx
    assert "lineup.py next" in run(repo, "status", str(a)).stdout


def test_adopt_takes_over_a_queued_spec(repo):
    a = spec(repo, "a")
    queue(repo, a)
    r = run(repo, "adopt", str(a), session="s2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(a.resolve()) in record("s2")
