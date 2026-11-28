"""夜の間の承認し直し（approve --by-advisor）を、入口（autopilot.py の CLI）から通して確かめる。
人が一度承認した spec の、block の後の承認し直しだけを、fable-advisor と advice-checker の起動の記録で通す。"""
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

from test_autopilot import GOOD_SPEC, PLUGIN, approved, init_spec, repo, run, state, user_says  # noqa: F401

sys.path.insert(0, str(PLUGIN / "scripts"))
import advisor_approval  # noqa: E402

OK_ADVISOR = "推奨: 案 A\n理由: 前提の取り違えを直すだけ\n承認: 可\n"
OK_CHECKER = "判定: 反証なし（確かめられない 0 / 3）\n主張ごとの結果:\n- 主張: 成り立つ — spec.md:3\n"
PREFIX = "相談役（fable-advisor・advice-checker 反証なし）: "


def stamp(ago=0.0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=ago)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def subagent_ran(name, reply, form="text", session="s1", ago=0.0, agent_type=None, tool_output="ok"):
    """host が subagent の記録（meta.json と transcript）を書く。最後の assistant の行に reply が入る（text か SubagentHandback）。"""
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / session / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    agent = f"agent-a{time.time_ns():x}"
    (sub / f"{agent}.meta.json").write_text(json.dumps({"agentType": agent_type or f"spec-autopilot:{name}"}), encoding="utf-8")
    block = ({"type": "text", "text": reply} if form == "text"
             else {"type": "tool_use", "id": "toolu_1", "name": "SubagentHandback", "input": {"message": reply}})
    rows = [{"type": "user", "timestamp": stamp(ago), "message": {"role": "user", "content": "相談"}},
            {"type": "assistant", "timestamp": stamp(ago), "message": {"model": "claude-fable-5-2", "content": [{"type": "thinking", "thinking": "..."}]}},
            {"type": "assistant", "timestamp": stamp(ago), "message": {"model": "claude-fable-5-2", "content": [block]}},
            {"type": "user", "timestamp": stamp(ago), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": tool_output}]}}]
    (sub / f"{agent}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    time.sleep(0.02)


def both_ran(advisor=OK_ADVISOR, checker=OK_CHECKER, form="text", tool_output="ok"):
    subagent_ran("fable-advisor", advisor, form, tool_output=tool_output)
    subagent_ran("advice-checker", checker, form, tool_output=tool_output)


def blocked_spec(repo):
    """人が承認した spec が block し、spec.md を直した後（承認し直しが要る）。"""
    d = approved(repo)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "前提の取り違え", "--evidence", "x").returncode == 0
    time.sleep(0.02)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("休憩中に遊べる", "休憩中に手軽に遊べる"), encoding="utf-8")
    time.sleep(0.02)
    return d


def by_advisor(repo, d, *extra):
    return run(repo, "approve", str(d), "--by", "前提を直した", "--by-advisor", *extra)


def out(r):
    return r.stdout + r.stderr


@pytest.mark.parametrize("form", ["text", "handback"])
def test_approve_by_advisor_returns_a_blocked_spec_to_building(repo, form):
    d = blocked_spec(repo)
    both_ran(form=form)
    r = by_advisor(repo, d)
    assert r.returncode == 0, out(r)
    s = state(d)
    assert s["phase"] == "building"
    assert s["approved_by"] == PREFIX + "前提を直した"
    assert s["history"][-1]["phase"] == "blocked"


def test_approve_by_advisor_uses_the_later_advisor_reply_when_it_was_asked_again(repo):
    d = blocked_spec(repo)
    subagent_ran("fable-advisor", "承認: 否\n")
    both_ran()
    assert by_advisor(repo, d).returncode == 0


def test_approve_by_advisor_refuses_when_the_later_advisor_reply_is_no(repo):
    d = blocked_spec(repo)
    both_ran()
    subagent_ran("fable-advisor", "承認: 否\n")
    subagent_ran("advice-checker", OK_CHECKER)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "承認: 可" in out(r) and state(d)["phase"] == "blocked"


@pytest.mark.parametrize("missing, advisor, checker, word", [
    ("fable-advisor が起動していない", None, OK_CHECKER, "fable-advisor"),
    ("advice-checker が起動していない", OK_ADVISOR, None, "advice-checker"),
    ("承認: 否", "承認: 否\n", OK_CHECKER, "承認: 可"),
    ("承認の行が無い", "推奨: 案 A\n", OK_CHECKER, "承認: 可"),
    ("反証あり", OK_ADVISOR, "判定: 反証あり（確かめられない 0 / 3）\n", "反証あり"),
    ("確かめられない 1", OK_ADVISOR, "判定: 反証なし（確かめられない 1 / 3）\n", "確かめられない"),
    ("判定の行が無い", OK_ADVISOR, "問題は見つからなかった\n", "判定"),
])
def test_approve_by_advisor_refuses_when_a_condition_is_missing(repo, missing, advisor, checker, word):
    d = blocked_spec(repo)
    if advisor is not None:
        subagent_ran("fable-advisor", advisor)
    if checker is not None:
        subagent_ran("advice-checker", checker)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and word in r.stdout, out(r)
    assert state(d)["phase"] == "blocked"


@pytest.mark.parametrize("name, advisor, checker, word", [
    ("否の後に別の問の可", "承認: 否\n理由: x\n承認: 可\n", OK_CHECKER, "承認:"),
    ("可の後に否", "承認: 可\n承認: 否\n", OK_CHECKER, "承認:"),
    ("可が 2 本", "承認: 可\n承認: 可\n", OK_CHECKER, "承認:"),
    ("否に理由を続けた行と可", "承認: 否（理由）\n承認: 可\n", OK_CHECKER, "承認:"),
    ("可に理由を続けた 1 本", "承認: 可（理由）\n", OK_CHECKER, "承認: 可"),
    ("反証ありの後に別の問の反証なし", OK_ADVISOR, "判定: 反証あり（確かめられない 0 / 3）\n判定: 反証なし（確かめられない 0 / 2）\n", "判定:"),
    ("反証なしの後に反証あり", OK_ADVISOR, "判定: 反証なし（確かめられない 0 / 3）\n判定: 反証あり（確かめられない 0 / 2）\n", "判定:"),
    ("反証なしが 2 本", OK_ADVISOR, OK_CHECKER + OK_CHECKER, "判定:"),
    ("形の外れた判定と反証なし", OK_ADVISOR, "判定: 保留\n判定: 反証なし（確かめられない 0 / 2）\n", "判定:"),
])
def test_approve_by_advisor_needs_exactly_one_approval_line_and_one_verdict_line(repo, name, advisor, checker, word):
    d = blocked_spec(repo)
    subagent_ran("fable-advisor", advisor)
    subagent_ran("advice-checker", checker)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and r.stdout.startswith("ERROR") and word in r.stdout, out(r)
    assert state(d)["phase"] == "blocked"


@pytest.mark.parametrize("late_name, late_reply", [("fable-advisor", "承認: 否\n"), ("advice-checker", OK_CHECKER)])
def test_approve_by_advisor_refuses_when_a_later_record_has_an_unreadable_meta_json(repo, late_name, late_reply):
    d = blocked_spec(repo)
    both_ran()
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    for bad in ("{", "[]", '{"agentType": 3}', ""):
        (sub / "agent-zzmeta.meta.json").write_text(bad, encoding="utf-8")
        (sub / "agent-zzmeta.jsonl").write_text(json.dumps({"type": "assistant", "timestamp": stamp(), "message": {"content": [{"type": "text", "text": late_reply}]}}) + "\n", encoding="utf-8")
        r = by_advisor(repo, d)
        assert r.returncode == 1 and "読めない" in r.stdout and state(d)["phase"] == "blocked", (bad, out(r))


def test_approve_by_advisor_ignores_an_unreadable_meta_json_written_before_the_last_change(repo):
    d = approved(repo)
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-zzold.meta.json").write_text("{", encoding="utf-8")
    time.sleep(0.05)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    time.sleep(0.02)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("休憩中に遊べる", "休憩中に手軽に遊べる"), encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    assert by_advisor(repo, d).returncode == 0


def test_approve_by_advisor_refuses_a_checker_launched_before_the_advisor(repo):
    d = blocked_spec(repo)
    subagent_ran("advice-checker", OK_CHECKER)
    subagent_ran("fable-advisor", OK_ADVISOR)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "advice-checker" in r.stdout and "より前" in r.stdout
    assert state(d)["phase"] == "blocked"


def test_approve_by_advisor_ignores_records_older_than_the_last_change_of_spec_md(repo):
    d = approved(repo)
    both_ran()  # spec.md の最後の変更より前
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    time.sleep(0.02)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("休憩中に遊べる", "休憩中に手軽に遊べる"), encoding="utf-8")
    time.sleep(0.02)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "fable-advisor" in r.stdout and state(d)["phase"] == "blocked"


def test_approve_by_advisor_ignores_records_older_than_the_block(repo):
    d = approved(repo)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("休憩中に遊べる", "休憩中に手軽に遊べる"), encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    time.sleep(0.02)
    assert run(repo, "block", str(d), "--req", "R1", "--reason", "x", "--evidence", "y").returncode == 0
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "fable-advisor" in r.stdout and state(d)["phase"] == "blocked"


def test_approve_by_advisor_ignores_records_of_another_session_and_another_agent(repo):
    d = blocked_spec(repo)
    subagent_ran("fable-advisor", OK_ADVISOR, session="other")
    subagent_ran("advice-checker", OK_CHECKER, session="other")
    subagent_ran("fable-advisor", OK_ADVISOR, agent_type="plain:not-fable-advisor")
    subagent_ran("advice-checker", OK_CHECKER, agent_type="plain:advice-checker-2")
    r = by_advisor(repo, d)
    assert r.returncode == 1 and state(d)["phase"] == "blocked"


def test_approve_by_advisor_refuses_an_unreadable_record(repo):
    d = blocked_spec(repo)
    both_ran()
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    (sub / "agent-zzbad.meta.json").write_text(json.dumps({"agentType": "spec-autopilot:fable-advisor"}), encoding="utf-8")
    (sub / "agent-zzbad.jsonl").write_text('{"type":"user","timestamp":"2099-01-01T00:00:00Z"}\n{"type":"assis', encoding="utf-8")
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "読めない" in r.stdout and state(d)["phase"] == "blocked"


# U+2028・U+2029・U+0085 は生の文字で書かず、エスケープで書く（生で書くと、このファイルを読んだ実装役の transcript が切れる）
LINE_SEPARATORS = ["\u2028", "\u2029", "\x85"]


@pytest.mark.parametrize("sep", LINE_SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_approve_by_advisor_reads_a_record_whose_tool_result_holds_a_line_separator(repo, sep):
    """読んだファイルの中身（user の tool_result の行）に生の改行に似た文字があっても、1 行として読み、返答の行で判定する。"""
    d = blocked_spec(repo)
    both_ran(tool_output=f"読んだ行 a{sep}b 終わり")
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    assert any(sep in f.read_text(encoding="utf-8") for f in sub.glob("*.jsonl"))  # 生の文字がファイルに残っている
    r = by_advisor(repo, d)
    assert r.returncode == 0, out(r)
    assert state(d)["phase"] == "building"


def test_approve_by_advisor_still_refuses_a_cut_line_in_a_record_with_a_line_separator(repo):
    """生の U+2028 を持つ行と、途中で切れた行が混ざる記録は、読めない記録として止める。"""
    d = blocked_spec(repo)
    both_ran(tool_output="a\u2028b")
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / "s1" / "subagents"
    (sub / "agent-zzbad.meta.json").write_text(json.dumps({"agentType": "spec-autopilot:advice-checker"}), encoding="utf-8")
    good = json.dumps({"type": "user", "timestamp": "2099-01-01T00:00:00Z", "message": {"content": "a\u2028b"}}, ensure_ascii=False)
    (sub / "agent-zzbad.jsonl").write_text(good + '\n{"type":"assis', encoding="utf-8")
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "読めない" in r.stdout and state(d)["phase"] == "blocked"


def test_approve_by_advisor_without_a_session_id_is_refused(repo):
    d = blocked_spec(repo)
    both_ran()
    r = run(repo, "approve", str(d), "--by", "x", "--by-advisor", session=None)
    assert r.returncode == 1 and state(d)["phase"] == "blocked"


# --- 人の返事が要る形 ---

def test_approve_by_advisor_refuses_the_first_approval_of_a_discovery_spec(repo):
    d = init_spec(repo)
    both_ran()
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "人の返事" in out(r) and state(d)["phase"] == "discovery"


def test_approve_by_advisor_refuses_a_queued_spec(repo):
    d = init_spec(repo)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    both_ran()
    r = by_advisor(repo, d, "--queue")
    assert r.returncode == 1 and "人の返事" in out(r) and state(d)["phase"] == "queued"


def test_approve_by_advisor_refuses_a_changed_scope_section(repo):
    d = blocked_spec(repo)
    text = (d / "spec.md").read_text(encoding="utf-8").replace("- 範囲: PR まで", "- 範囲: マージまで")
    (d / "spec.md").write_text(text, encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "自走の範囲" in out(r) and "人の返事" in out(r) and state(d)["phase"] == "blocked"


def test_approve_by_advisor_accepts_a_scope_section_that_only_gained_a_comment(repo):
    d = blocked_spec(repo)
    text = (d / "spec.md").read_text(encoding="utf-8").replace("- 範囲: PR まで", "<!-- 注 -->\n- 範囲: PR まで")
    (d / "spec.md").write_text(text, encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    assert by_advisor(repo, d).returncode == 0


def test_approve_by_advisor_refuses_a_spec_approved_before_the_scope_was_recorded(repo):
    d = blocked_spec(repo)
    s = state(d)
    del s["scope_sha256"]
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    both_ran()
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "人の返事" in out(r) and state(d)["phase"] == "blocked"


def test_approve_by_advisor_refuses_a_done_spec(repo):
    d = approved(repo)
    s = state(d)
    s.update(phase="done", done_at=time.time())
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    both_ran()
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "人の返事" in out(r) and state(d)["phase"] == "done"


# --- 自走の範囲の節の記録 ---

def test_human_approval_records_the_scope_section_hash(repo):
    d = approved(repo)
    import autopilot
    assert state(d)["scope_sha256"] == advisor_approval.scope_sha(autopilot.section((d / "spec.md").read_text(encoding="utf-8"), "自走の範囲"))


def test_human_reapproval_after_a_scope_change_records_the_new_hash(repo):
    d = blocked_spec(repo)
    before = state(d)["scope_sha256"]
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8").replace("- 範囲: PR まで", "- 範囲: マージまで"), encoding="utf-8")
    time.sleep(0.02)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "範囲を広げる").returncode == 0
    assert state(d)["scope_sha256"] != before


def test_queue_approval_records_the_scope_hash_and_survives_a_lineup_block(repo):
    d = init_spec(repo)
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK", "--queue").returncode == 0
    s = state(d)
    assert s["scope_sha256"]
    s.update(phase="blocked", approved_at=None, blocked={"req": "着手", "reason": "x", "evidence": "y", "at": time.time()})
    (d / "state.json").write_text(json.dumps(s), encoding="utf-8")
    time.sleep(0.02)
    (d / "spec.md").write_text((d / "spec.md").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    time.sleep(0.02)
    both_ran()
    assert by_advisor(repo, d).returncode == 0
    assert state(d)["phase"] == "building"


def test_approve_without_by_advisor_still_needs_a_human_utterance_after_block(repo):
    d = blocked_spec(repo)
    both_ran()
    r = run(repo, "approve", str(d), "--by", "自分で")
    assert r.returncode != 0 and state(d)["phase"] == "blocked"


# --- 返答を読む関数 ---

def test_launches_read_the_last_reply_in_text_and_handback_forms(repo):
    for form in ("text", "handback"):
        subagent_ran("fable-advisor", "承認: 可\n日本語の返答", form, session=f"x-{form}")
    for form in ("text", "handback"):
        got = advisor_approval.launches(f"x-{form}", 0.0)
        assert [(n, r) for n, _, r in got] == [("fable-advisor", "承認: 可\n日本語の返答")]


def test_reply_errors_is_a_function_of_the_session_and_since_only(repo):
    both_ran()
    assert advisor_approval.reply_errors("s1", 0.0) == []
    assert advisor_approval.reply_errors("s1", time.time() + 10)  # 記録より後の since なら、起動の記録が無い


# --- 文書の形とコードが読む形の突き合わせ ---

def _advisor_output_section():
    text = (PLUGIN / "agents" / "fable-advisor.md").read_text(encoding="utf-8")
    return text.split("\n## 出力", 1)[1]


def test_fable_advisor_definition_names_the_approval_lines_the_code_reads(repo):
    """fable-advisor.md の出力の欄に書いた `承認: 可`・`承認: 否` の文字列を、そのまま返答に使うと、コードがそのとおりに読む。"""
    section = _advisor_output_section()
    assert "`承認: 可`" in section and "`承認: 否`" in section
    d = blocked_spec(repo)
    both_ran(advisor="推奨: 案 A\n" + "承認: 否" + "\n")
    r = by_advisor(repo, d)
    assert r.returncode != 0 and "承認: 可" in out(r) and state(d)["phase"] == "blocked"
    both_ran(advisor="推奨: 案 A\n" + "承認: 可" + "\n")
    assert by_advisor(repo, d).returncode == 0


def test_commands_autopilot_gives_the_two_stage_night_procedure_with_flags_the_cli_accepts(repo):
    text = (PLUGIN / "commands" / "autopilot.md").read_text(encoding="utf-8")
    section = text.split("\n## 人に戻るとき", 1)[1]
    for word in ("fable-advisor", "advice-checker", "--by-advisor", "lineup.py next", "朝の報告"):
        assert word in section, word
    assert "--by-advisor" in run(repo, "approve", "--help").stdout


def test_advice_checker_definition_gives_one_verdict_line_form_that_the_gate_accepts(repo):
    """advice-checker.md の出力の節の判定の行（`判定:`・`反証なし`・括弧の形）を確かめられない 0 で埋めた行は、門が通す。
    出力の節の外には、判定の行の形（`判定: 反証あり`・`判定: 反証なし` で始まる literal）が無い（形の正本が 1 か所）。"""
    before, section = (PLUGIN / "agents" / "advice-checker.md").read_text(encoding="utf-8").split("\n## 出力", 1)
    head = re.search(r"- `(判定:)` `反証あり` / `(反証なし)` に続けて `(（確かめられない <n> / <主張の数>）)`", section)
    assert head, "出力の節から `判定:`・`反証なし`・括弧の形が読み出せない"
    label, verdict, paren = head.groups()
    line = label + " " + verdict + paren.replace("<n>", "0").replace("<主張の数>", "3")
    d = blocked_spec(repo)
    both_ran(checker=line + "\n主張ごとの結果:\n- 主張: 成り立つ — spec.md:3\n")
    r = by_advisor(repo, d)
    assert r.returncode == 0, out(r)
    assert state(d)["phase"] == "building"
    assert re.findall(r"`判定: 反証(?:あり|なし)", before) == []


@pytest.mark.parametrize("advisor_name", ["fable-advisor-high", "fable-advisor-opus"])
def test_approve_by_advisor_counts_the_advisor_of_every_stage_in_the_table(repo, advisor_name):
    d = blocked_spec(repo)
    subagent_ran(advisor_name, OK_ADVISOR)
    subagent_ran("advice-checker", OK_CHECKER)
    r = by_advisor(repo, d)
    assert r.returncode == 0, out(r)
    assert state(d)["phase"] == "building"


@pytest.mark.parametrize("other", ["opus-advisor", "fable-advisor-xhigh", "autopilot-reviewer"])
def test_approve_by_advisor_does_not_count_an_agent_that_is_not_in_the_stage_table(repo, other):
    d = blocked_spec(repo)
    subagent_ran(other, OK_ADVISOR)
    subagent_ran("advice-checker", OK_CHECKER)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "fable-advisor" in r.stdout and state(d)["phase"] == "blocked"


def test_approve_by_advisor_uses_the_last_advisor_record_across_the_stage_names(repo):
    d = blocked_spec(repo)
    subagent_ran("fable-advisor-high", OK_ADVISOR)
    subagent_ran("fable-advisor-opus", "承認: 否\n")
    subagent_ran("advice-checker", OK_CHECKER)
    r = by_advisor(repo, d)
    assert r.returncode == 1 and "承認: 可" in out(r) and state(d)["phase"] == "blocked"
