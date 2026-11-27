"""複数の spec をまとめて承認し（approve --queue）、夜の間に 1 本ずつ着手する（lineup.py next）流れを、
入口（autopilot.py・lineup.py の CLI、Stop hook、SessionStart hook）から通して確かめる。"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_autopilot import (EXISTING_SECTIONS, GOOD_SPEC, PLUGIN, existing_repo, init_spec, make_done, repo, run, state,  # noqa: F401
                           stop_hook, user_says)
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


# --- 依る spec は state.json に名前で書く ---

def test_queue_writes_only_the_directory_name_of_the_dependency_to_state_json(repo, tmp_path):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    b = spec(wb, "b", after=a, size="M")
    queue(wb, b)
    assert state(b)["after"] == a.name and "/" not in state(b)["after"]
    raw = (b / "state.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in raw and str(repo) not in raw and str(a.resolve()) not in raw


def test_next_starts_a_dependent_spec_in_another_worktree_from_the_name_in_state_json(repo, tmp_path):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    b = spec(wb, "b", after=a, size="M")
    queue(wb, b)
    assert state(b)["after"] == a.name
    assert line(repo, "next").returncode == 0
    set_phase(a, phase="done", done_at=time.time())
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "building"


def test_next_still_reads_an_absolute_path_left_in_after_by_the_earlier_version(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="blocked", blocked={"req": "R1", "reason": "x", "evidence": "y", "at": time.time()})
    set_phase(b, after=str(a.resolve()))
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and a.name in state(b)["blocked"]["reason"]


def test_next_blocks_a_dependent_spec_whose_dependency_is_not_in_the_session_record(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="done", done_at=time.time())
    set_phase(b, after="2026-01-01-no-such-spec")
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and "2026-01-01-no-such-spec" in state(b)["blocked"]["reason"]


def test_next_blocks_a_dependent_spec_whose_dependency_name_matches_two_specs(repo, tmp_path):
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    wb = tmp_path / "wb"
    subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(wb)], cwd=repo, check=True)
    twin = spec(wb, "a")
    assert twin.name == a.name
    queue(wb, twin)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="done", done_at=time.time())
    set_phase(twin, phase="done", done_at=time.time())
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and a.name in state(b)["blocked"]["reason"]


def test_demand_does_not_count_a_dependent_spec_whose_dependency_cannot_be_found(repo):
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import lineup

    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="done", done_at=time.time())
    assert lineup.demand([(a, state(a)), (b, state(b))], set()) is not None  # 依る spec が引けるうちは、着手できるものに数える
    set_phase(b, after="2026-01-01-no-such-spec")
    assert lineup.demand([(a, state(a)), (b, state(b))], set()) is None


def test_stop_hook_does_not_demand_next_for_a_dependent_spec_whose_dependency_cannot_be_found(repo):
    a = spec(repo, "a")
    queue(repo, a)
    b = spec(repo, "b", after=a, size="M")
    queue(repo, b)
    set_phase(a, phase="done", done_at=time.time())
    assert "lineup.py next" in decision(repo).get("reason", "")  # b は a が終わったので着手できる
    set_phase(b, after="2026-01-01-no-such-spec")
    reason = decision(repo).get("reason", "")
    assert "lineup.py next" not in reason and "読めない" not in reason


# --- 依る spec が done・block で記録から外れた後も、enqueue で repo の外に書いた対から引く ---

def finish(repo, d):
    """next で着手した spec を、実物の cmd_done で終える（記録から外れる）。"""
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(d.resolve()) not in record()


def dependent_pair(repo, tmp_path, same_worktree):
    """a（依る spec）と、a に依る b を承認し、a に着手して返す。b は別の worktree のこともある。"""
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "c0"], cwd=repo, check=True)
    a = spec(repo, "a")
    queue(repo, a)
    home = repo
    if not same_worktree:
        home = tmp_path / "wb"
        subprocess.run([*GIT, "worktree", "add", "-q", "-b", "b", str(home)], cwd=repo, check=True)
    b = spec(home, "b", after=a, size="M")
    queue(home, b)
    assert line(repo, "next").returncode == 0 and state(a)["phase"] == "building"
    return a, b


@pytest.mark.parametrize("same_worktree", [True, False], ids=["same_worktree", "other_worktree"])
def test_next_starts_a_dependent_spec_after_cmd_done_dropped_its_dependency_from_the_record(repo, tmp_path, same_worktree):
    a, b = dependent_pair(repo, tmp_path, same_worktree)
    finish(repo, a)
    if not same_worktree:  # 載せ替えで a の commit が持ち込む ADR を、b の worktree の未追跡の写しが塞がないようにする
        (b.parents[2] / "docs" / "adr" / "2026-01-01-game.md").unlink()
    assert "lineup.py next" in decision(repo).get("reason", "")  # Stop hook も b を着手できるものに数える
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "building" and state(b)["after"] == a.name, state(b).get("blocked", {}).get("reason")


def test_next_blocks_a_dependent_spec_after_cmd_block_dropped_its_dependency_from_the_record(repo, tmp_path):
    a, b = dependent_pair(repo, tmp_path, True)
    r = run(repo, "block", str(a), "--req", "R1", "--reason", "x", "--evidence", "y")
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(a.resolve()) not in record()
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and "が block" in state(b)["blocked"]["reason"]


@pytest.mark.parametrize("end", ["done", "block"])
def test_no_state_json_of_the_dependent_pair_holds_a_local_path_after_queue_start_and_end(repo, tmp_path, end):
    """同じ種類（state.json に手元のパスが入る）の洗い出し: 承認・着手・依る spec の終わり・次の着手か block を通しても、
    両方の state.json のどこにも絶対パスが入らない。"""
    a, b = dependent_pair(repo, tmp_path, False)
    if end == "done":
        finish(repo, a)
        (b.parents[2] / "docs" / "adr" / "2026-01-01-game.md").unlink()
    else:
        assert run(repo, "block", str(a), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    assert line(repo, "next").returncode == 0
    assert state(b)["phase"] == ("building" if end == "done" else "blocked")
    for d in (a, b):
        raw = (d / "state.json").read_text(encoding="utf-8")
        assert str(tmp_path) not in raw and str(repo) not in raw and str(Path.home()) not in raw, d.name


def test_next_blocks_when_the_pair_written_at_the_queue_names_another_spec_than_after(repo, tmp_path):
    a, b = dependent_pair(repo, tmp_path, True)
    finish(repo, a)
    set_phase(b, after="2026-01-01-no-such-spec")  # 対の先の名前が after と違うので使わない
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and "2026-01-01-no-such-spec" in state(b)["blocked"]["reason"]


def test_next_blocks_when_the_dependency_directory_of_the_pair_is_gone(repo, tmp_path):
    a, b = dependent_pair(repo, tmp_path, True)
    finish(repo, a)
    shutil.rmtree(a)
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(b)["phase"] == "blocked" and a.name in state(b)["blocked"]["reason"]


def test_demand_does_not_count_a_dependent_spec_whose_dependency_directory_of_the_pair_is_gone(repo, tmp_path):
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import lineup

    a, b = dependent_pair(repo, tmp_path, True)
    finish(repo, a)
    assert lineup.demand([(b, state(b))], set()) is not None
    shutil.rmtree(a)
    assert lineup.demand([(b, state(b))], set()) is None


BROKEN_PAIRS = [("{broken", "lineup-after.json が読めない"), ("", "lineup-after.json が読めない"),
                ("[]", "lineup-after.json の形が読めない"), ("null", "lineup-after.json の形が読めない"),
                ('"x"', "lineup-after.json の形が読めない"), ('{"/x": 1}', "lineup-after.json の形が読めない")]
BROKEN_STATES = ["{broken", "", "[]", "null"]


def broken_pairs(repo, tmp_path, content):
    """a を done で記録から外し、repo の外の対のファイルを content に書き換える。"""
    a, b = dependent_pair(repo, tmp_path, True)
    finish(repo, a)
    (Path(os.environ["SPEC_AUTOPILOT_HOME"]) / "lineup-after.json").write_text(content, encoding="utf-8")
    return a, b


def broken_dependency_state(repo, tmp_path, content):
    a, b = dependent_pair(repo, tmp_path, True)
    finish(repo, a)
    (a / "state.json").write_text(content, encoding="utf-8")
    return a, b


@pytest.mark.parametrize("content,phrase", BROKEN_PAIRS)
def test_next_blocks_with_the_reason_that_lineup_after_json_cannot_be_read(repo, tmp_path, content, phrase):
    a, b = broken_pairs(repo, tmp_path, content)
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    reason = state(b)["blocked"]["reason"]
    assert state(b)["phase"] == "blocked" and phrase in reason and "記録に無いか" not in reason, reason
    assert str(repo) not in reason and str(Path.home()) not in reason  # state.json は commit されるので、手元のパスを書かない


@pytest.mark.parametrize("content,phrase", BROKEN_PAIRS)
def test_stop_hook_says_the_line_cannot_be_read_when_lineup_after_json_is_broken(repo, tmp_path, content, phrase):
    broken_pairs(repo, tmp_path, content)
    out = decision(repo)
    assert out.get("decision") == "block" and "行列を読めない" in out["reason"], out


@pytest.mark.parametrize("content", BROKEN_STATES)
def test_next_blocks_with_the_reason_that_the_state_json_of_the_dependency_cannot_be_read(repo, tmp_path, content):
    a, b = broken_dependency_state(repo, tmp_path, content)
    r = line(repo, "next")
    assert r.returncode == 0, r.stdout + r.stderr
    reason = state(b)["blocked"]["reason"]
    assert state(b)["phase"] == "blocked" and f"依る spec {a.name} の state.json が読めない" in reason and "記録に無いか" not in reason, reason
    assert str(repo) not in reason and str(Path.home()) not in reason


@pytest.mark.parametrize("content", BROKEN_STATES)
def test_stop_hook_says_the_line_cannot_be_read_when_the_state_json_of_the_dependency_is_broken(repo, tmp_path, content):
    broken_dependency_state(repo, tmp_path, content)
    out = decision(repo)
    assert out.get("decision") == "block" and "行列を読めない" in out["reason"], out


def test_concurrent_queues_keep_every_pair_written_to_the_file_outside_the_repo(repo):
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import lineup; from pathlib import Path; "
            "lineup.remember(Path(sys.argv[2]), Path(sys.argv[3]))")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(PLUGIN / "scripts"), f"/x/later-{i}", f"/y/dep-{i}"])
             for i in range(8)]
    assert [p.wait(timeout=60) for p in procs] == [0] * 8
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import lineup

    assert lineup.pairs() == {f"/x/later-{i}": f"/y/dep-{i}" for i in range(8)}


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
