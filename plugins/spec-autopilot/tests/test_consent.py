"""承認の門の起点を、承認の中身のハッシュを lint が初めて見た時刻にする（R1・R2）。入口（lint・approve の CLI）から確かめる。"""
import json
import subprocess
import sys
import time

from test_autopilot import CLI, GOOD_SPEC, PLUGIN, approved, init_spec, repo, run, state, user_says  # noqa: F401（repo は fixture）

sys.path.insert(0, str(PLUGIN / "scripts"))
import consent  # noqa: E402

OLD, NEW = "docs/adr/0007-game.md", "docs/adr/0008-game.md"
NUMBERED = GOOD_SPEC.replace("docs/adr/2026-01-01-game.md", OLD)


def numbered_spec(repo, d):
    """連番の ADR（0007）を指す spec にする。"""
    (repo / OLD).write_text("# ADR: canvas で描く\n\n- 直し方: 要らなくする\n", encoding="utf-8")
    (d / "spec.md").write_text(NUMBERED, encoding="utf-8")


def renumber(repo, d, text=NUMBERED):
    """改番: ADR のファイルを 0008 に改め、spec の先頭の行の連番だけを直す（text で本文を変えられる）。"""
    (repo / OLD).rename(repo / NEW)
    (d / "spec.md").write_text(text.replace(OLD, NEW), encoding="utf-8")


def lint_ok(repo, d):
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    time.sleep(0.02)


def approve(repo, d):
    return run(repo, "approve", str(d), "--by", "OK")


def test_content_sha_ignores_only_the_adr_number_digits_in_the_head():
    base = consent.content_sha(NUMBERED)
    assert consent.content_sha(NUMBERED.replace(OLD, NEW)) == base
    assert consent.content_sha(NUMBERED.replace("game.md", "other.md")) != base  # slug は残す
    assert consent.content_sha(NUMBERED.replace("列を消す", "列を消去する")) != base
    assert consent.content_sha(NUMBERED.replace("canvas で描く", "DOM で描く")) != base  # 作り方の節も含める


def test_lint_records_the_hash_once_and_only_when_it_passes(repo):
    d = init_spec(repo)
    numbered_spec(repo, d)
    (d / "spec.md").write_text(NUMBERED.replace("## 要件", "## 要件の間違い"), encoding="utf-8")
    assert run(repo, "lint", str(d)).returncode == 1
    assert "consent" not in state(d)
    (d / "spec.md").write_text(NUMBERED, encoding="utf-8")
    lint_ok(repo, d)
    first = state(d)["consent"]
    assert first["sha256"] == consent.content_sha(NUMBERED)
    lint_ok(repo, d)
    assert state(d)["consent"] == first  # 同じハッシュでは時刻を書き換えない
    (d / "spec.md").write_text(NUMBERED + "\n補足\n", encoding="utf-8")
    lint_ok(repo, d)
    assert state(d)["consent"]["sha256"] != first["sha256"] and state(d)["consent"]["at"] > first["at"]


def test_approve_does_not_record_the_hash_by_its_inner_lint(repo):
    d = init_spec(repo)
    user_says(repo)
    assert approve(repo, d).returncode == 0
    assert "consent" not in state(d)


def test_approve_passes_after_only_the_adr_number_is_fixed_when_linted_before_the_human_replied(repo):
    d = init_spec(repo)
    numbered_spec(repo, d)
    lint_ok(repo, d)
    user_says(repo)
    time.sleep(0.02)
    renumber(repo, d)
    r = approve(repo, d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["phase"] == "building"


def test_approve_asks_for_a_new_reply_when_text_other_than_the_adr_number_changes(repo):
    for slug, old, new in (("req", "横 1 列がそろったとき", "横 2 列がそろったとき"),  # 要件の文
                           ("how", "規則を純粋な JS に分け", "規則を純粋な TS に分け")):  # 作り方の節
        d = init_spec(repo, slug)
        numbered_spec(repo, d)
        lint_ok(repo, d)
        user_says(repo)
        time.sleep(0.02)
        renumber(repo, d, NUMBERED.replace(old, new))
        r = approve(repo, d)
        assert r.returncode != 0 and "人の発言が記録されていない" in r.stdout + r.stderr, old
        assert state(d)["phase"] == "discovery"
        (repo / NEW).rename(repo / OLD)


def test_approve_asks_for_a_reply_when_the_spec_was_not_linted_before_it(repo):
    d = init_spec(repo)
    numbered_spec(repo, d)
    user_says(repo)
    time.sleep(0.02)
    renumber(repo, d)
    r = approve(repo, d)
    assert r.returncode != 0 and "人の発言が記録されていない" in r.stdout + r.stderr
    user_says(repo)
    assert approve(repo, d).returncode == 0


def test_a_block_after_the_record_still_needs_a_reply_after_the_block(repo):
    d = init_spec(repo)
    lint_ok(repo, d)
    user_says(repo)
    assert approve(repo, d).returncode == 0
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    r = approve(repo, d)
    assert r.returncode != 0 and "blockの後に人の発言が記録されていない" in r.stdout + r.stderr
    user_says(repo)
    assert approve(repo, d).returncode == 0


def test_a_broken_record_is_kept_aside_and_replaced_and_does_not_open_the_gate(repo):
    d = init_spec(repo)
    s = state(d)
    s["consent"] = {"sha256": consent.content_sha(GOOD_SPEC), "at": "あとで"}
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    user_says(repo)
    time.sleep(0.02)
    (d / "spec.md").write_text(GOOD_SPEC, encoding="utf-8")  # mtime を人の発言の後にする
    assert approve(repo, d).returncode != 0  # 壊れた記録は起点にせず、spec.md の最後の変更に戻る
    r = run(repo, "lint", str(d))
    assert r.returncode == 0 and "consent" in r.stdout
    kept = list(d.glob("state.json.consent-broken-*"))
    assert len(kept) == 1 and json.loads(kept[0].read_text(encoding="utf-8"))["at"] == "あとで"
    assert consent.valid(state(d)["consent"])
    lint_ok(repo, d)  # 2 回目は直った記録を残す。退避は増えない
    assert len(list(d.glob("state.json.consent-broken-*"))) == 1


def test_concurrent_lints_keep_the_other_keys_and_the_first_seen_time(repo):
    d = init_spec(repo)
    s = state(d)
    s["note"] = "別のプロセスが書いた値"
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    procs = [subprocess.Popen([sys.executable, str(CLI), "lint", str(d)], cwd=repo, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) for _ in range(8)]
    assert [p.wait() for p in procs] == [0] * 8
    after = state(d)  # 壊れた JSON なら ここで落ちる
    assert after["note"] == "別のプロセスが書いた値" and consent.valid(after["consent"])
    lint_ok(repo, d)
    assert state(d)["consent"] == after["consent"]
