"""合意の ADR の直し方の段の行（R1〜R5）を、lint と 3 つの承認の入口から確かめる。"""
import json
import sys

from test_autopilot import GOOD_SPEC, PLUGIN, approved, init_spec, make_done, repo, run, state, three_fails, user_says  # noqa: F401（repo は fixture）
from test_lineup import line, spec as lineup_spec
from test_light import light

sys.path.insert(0, str(PLUGIN / "scripts"))
import rootcause  # noqa: E402

ORDER = ["要らなくする", "入力の約束を変える", "設計を変える", "局所の継ぎ足し"]
ADR = "docs/adr/2026-01-01-game.md"


def put_adr(repo, *lines):
    (repo / ADR).write_text("# ADR: 合意\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def lint(repo, d):
    r = run(repo, "lint", str(d))
    return r.returncode, r.stdout + r.stderr


def test_lint_errors_when_the_fix_line_is_missing_or_not_exactly_one(repo):
    d = init_spec(repo)
    for lines in ([], ["- 直し方: 根本"], ["- 直し方: 要らなくする", "- 直し方: 設計を変える"]):
        put_adr(repo, *lines)
        code, out = lint(repo, d)
        assert code != 0 and "- 直し方:" in out, out


def test_lint_lists_every_missing_rejected_stage_and_passes_when_complete(repo):
    d = init_spec(repo)
    put_adr(repo, "- 直し方: 局所の継ぎ足し", "- 退けた: 要らなくする（既存の設定で目的に届かない）")
    code, out = lint(repo, d)
    assert code != 0
    assert "入力の約束を変える" in out and "設計を変える" in out and "要らなくする（<理由>）" not in out
    put_adr(repo, "- 直し方: 局所の継ぎ足し", "- 退けた: 要らなくする（a）", "- 退けた: 入力の約束を変える（b）",
            "- 退けた: 設計を変える（c）")
    assert lint(repo, d)[0] == 0


def test_lint_passes_with_the_top_stage_and_no_rejected_lines(repo):
    d = init_spec(repo)
    put_adr(repo, "- 直し方: 要らなくする")
    assert lint(repo, d)[0] == 0


def test_every_approval_is_refused_while_the_adr_lacks_the_lines(repo):
    d = init_spec(repo)
    put_adr(repo, "- 直し方: 設計を変える")
    user_says(repo)
    for args in (("--by", "OK"), ("--by", "OK", "--queue")):
        r = run(repo, "approve", str(d), *args)
        assert r.returncode != 0 and "退けた" in r.stdout + r.stderr, r.stdout + r.stderr
        assert state(d)["phase"] in ("discovery",)
    r = light(repo, "approve", str(d), "--source", "x")
    assert r.returncode != 0 and "退けた" in r.stdout + r.stderr
    assert state(d)["phase"] == "discovery"


def test_requirement_sentence_rejection_is_a_note_not_an_error_and_has_no_park_command(repo):
    d = init_spec(repo)
    put_adr(repo, "- 直し方: 設計を変える", "- 要件の文で退けた: 要らなくする（R2 の「Enter で再開」）",
            "- 退けた: 入力の約束を変える（y）")
    code, out = lint(repo, d)
    assert code == 0, out
    note = [l for l in out.splitlines() if l.startswith("NOTE:") and "要らなくする" in l]
    assert len(note) == 1 and "R2" in note[0] and "Enter で再開" in note[0]
    assert "overnight.py" not in out and " park " not in out


def test_the_check_is_skipped_after_approval_in_building_blocked_and_done(repo):
    d = approved(repo)
    put_adr(repo, "# 段の行なし")
    assert state(d)["phase"] == "building"
    assert "直し方" not in lint(repo, d)[1]
    assert "直し方" not in run(repo, "check", str(d)).stdout
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    assert state(d)["phase"] == "blocked"
    assert "直し方" not in lint(repo, d)[1]
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert "直し方" not in r.stdout + r.stderr and r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    assert "直し方" not in lint(repo, d)[1]
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert "直し方" not in r.stdout + r.stderr and r.returncode == 0, r.stdout + r.stderr


def test_goal_approval_does_not_need_the_lines(repo):
    d = init_spec(repo)
    put_adr(repo, "# 段の行なし")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "目的 OK", "--goal")
    assert "直し方" not in r.stdout + r.stderr


def test_no_adr_line_or_missing_file_gives_no_fix_error_and_approve_stops_on_the_old_message(repo):
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- ADR: docs/adr/2026-01-01-game.md\n", ""), encoding="utf-8")
    assert "直し方" not in lint(repo, d)[1]
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode != 0 and "spec.md の先頭に `- ADR:" in r.stdout + r.stderr and "直し方" not in r.stdout + r.stderr
    (d / "spec.md").write_text(GOOD_SPEC.replace("2026-01-01-game.md", "2026-01-01-none.md"), encoding="utf-8")
    assert "直し方" not in lint(repo, d)[1]
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode != 0 and "ADR docs/adr/2026-01-01-none.md が無い" in r.stdout + r.stderr


def test_a_queued_spec_whose_adr_lacks_the_lines_is_blocked_at_start(repo):
    d = lineup_spec(repo, "game")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    put_adr(repo, "- 直し方: 設計を変える")
    assert lint(repo, d)[0] != 0
    line(repo, "next")
    s = state(d)
    assert s["phase"] == "blocked" and "着手の時点で lint が通らない" in json.dumps(s, ensure_ascii=False) and "退けた" in json.dumps(s, ensure_ascii=False)


def test_consent_returns_errors_and_notes_from_the_adr_text():
    errs, notes = rootcause.consent_check("- 直し方: 設計を変える\n- 要件の文で退けた: 要らなくする（R1 の「列」）\n")
    assert len(errs) == 1 and "入力の約束を変える" in errs[0] and notes == []
    errs, notes = rootcause.consent_check("- 直し方: 設計を変える\n- 要件の文で退けた: 要らなくする（R1 の「列」）\n- 退けた: 入力の約束を変える（x）\n")
    assert errs == [] and len(notes) == 1 and "R1" in notes[0] and "列" in notes[0]


def _template_lines():
    text = (PLUGIN / "references" / "adr-template.md").read_text(encoding="utf-8")
    return text, [l.strip() for l in text.splitlines() if l.startswith(("- 直し方:", "- 退けた:", "- 要件の文で退けた:"))]


def test_adr_template_line_examples_pass_the_consent_lint_when_filled(repo):
    text, lines = _template_lines()
    assert len(lines) == 3
    # 直し方は入力の約束を変える、退けた行はその上の「要らなくする」で埋める
    filled = [l.replace("<段>", "入力の約束を変える" if l.startswith("- 直し方") else "要らなくする")
              .replace("<理由>", "既存の設定で目的に届かない").replace("R<n>", "R1").replace("<要件の語>", "語") for l in lines]
    errs, notes = rootcause.consent_check("\n".join(filled) + "\n")
    assert errs == [] and len(notes) == 1
    d = init_spec(repo)
    put_adr(repo, *filled)
    assert lint(repo, d)[0] == 0


def test_lint_passes_when_the_adr_lines_are_separated_by_crlf(repo):
    d = init_spec(repo)
    rows = ["- 直し方: 設計を変える", "- 退けた: 要らなくする（a）", "- 退けた: 入力の約束を変える（b）"]
    (repo / ADR).write_bytes("\r\n".join(["# ADR: 合意", ""] + rows + [""]).encode("utf-8"))
    code, out = lint(repo, d)
    assert code == 0, out


def test_an_adr_with_bytes_that_are_not_utf8_is_an_error_not_a_traceback_in_lint_and_every_approval(repo):
    d = init_spec(repo)
    for body in (b"# ADR\n\n- \xe7\x9b\xb4\xe3\x81\x97\xe6\x96\xb9: \xff\xfe\n", b"\xff\xfe\x00\x80 binary", b"- \xe7\x9b\xb4\xe3\x81\x97\xe6\x96\xb9: \xe8\xa6\x81\xe3\x82\x89\xe3\x81\xaa\xe3\x81\x8f\xe3\x81\x99\xe3\x82\x8b\n\xff\n"):
        (repo / ADR).write_bytes(body)
        code, out = lint(repo, d)
        assert "Traceback" not in out, out
        user_says(repo)
        for args in (("approve", str(d), "--by", "OK"), ("approve", str(d), "--by", "OK", "--queue")):
            r = run(repo, *args)
            assert "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
            assert state(d)["phase"] == "discovery"
        r = light(repo, "approve", str(d), "--source", "x")
        assert "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
        assert state(d)["phase"] == "discovery"
    (repo / ADR).write_bytes(b"# ADR\n\n- \xe7\x9b\xb4\xe3\x81\x97\xe6\x96\xb9: \xff\xfe\n")
    code, out = lint(repo, d)
    assert code != 0 and "UTF-8 で読めない" in out


def test_rework_with_an_adr_that_is_not_utf8_stops_with_a_message_not_a_traceback(repo):
    d = approved(repo)
    make_done(repo, d)
    three_fails(repo, d)
    (repo / "docs/adr/bad.md").write_bytes(b"- \xe7\x9b\xb4\xe3\x81\x97\xe6\x96\xb9: \xff\n")
    r = run(repo, "rework", str(d), "--req", "R1", "--adr", "docs/adr/bad.md")
    assert "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
    assert r.returncode != 0 and "UTF-8" in r.stdout + r.stderr


def test_an_adr_without_read_permission_is_an_error_not_a_traceback_in_lint_and_every_approval(repo):
    d = init_spec(repo)
    put_adr(repo, "- 直し方: 要らなくする")
    (repo / ADR).chmod(0o000)
    try:
        code, out = lint(repo, d)
        assert "Traceback" not in out and code != 0 and "読めない" in out, out
        user_says(repo)
        for args in (("approve", str(d), "--by", "OK"), ("approve", str(d), "--by", "OK", "--queue")):
            r = run(repo, *args)
            assert "Traceback" not in r.stdout + r.stderr and r.returncode != 0 and "読めない" in r.stdout + r.stderr, r.stdout + r.stderr
            assert state(d)["phase"] == "discovery"
        r = light(repo, "approve", str(d), "--source", "x")
        assert "Traceback" not in r.stdout + r.stderr and r.returncode != 0 and "読めない" in r.stdout + r.stderr, r.stdout + r.stderr
        assert state(d)["phase"] == "discovery"
    finally:
        (repo / ADR).chmod(0o644)


def test_an_empty_adr_is_an_error_about_the_missing_fix_line_in_lint(repo):
    d = init_spec(repo)
    (repo / ADR).write_bytes(b"")
    code, out = lint(repo, d)
    assert code != 0 and "- 直し方:" in out and "Traceback" not in out, out
