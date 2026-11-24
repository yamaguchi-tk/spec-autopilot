#!/usr/bin/env python3
"""中断・compaction の後に、自走中の spec の状態を新しい文脈に渡す SessionStart hook。

- 起動・再開・compaction・clear のどれでも動く。見る spec は、このセッションの記録と cwd の repo の spec
- 壁打ち中（discovery）・自走中（building）・確認待ち（wait）・人に戻した（blocked）・着手待ち（queued）の spec の状態（autopilot.py status）を additionalContext に入れる
- 記録には足さない。このセッションの記録に無い自走中・確認待ちの spec（fork・同じ repo の別のセッション・/clear の後）は、
  予算に触らず、場所と phase だけを出し、続ける指示を出さない。引き継ぐのは、人がそのセッションで引き継ぐと言ったときの autopilot.py adopt だけ
- 起動（startup）と再開（resume）では、このセッションの記録にある自走中の spec の、最後の活動から今までを予算から外す（中断の時間を数えない）
- 状態は repo のファイルが正本で、会話の記憶には頼らせない
- spec の有無によらず、人に返事を求める前に相談役へ聞く規則（ADVISE）を毎回渡す（plugin を入れた全 repo に届く場所がここだけのため）
- 止めない。読めない spec はその旨を渡し、hook 自体が読めないときは systemMessage と ADVISE を出す。出力は ASCII の JSON
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

HEADER = ("spec-autopilot: 続きのある spec がある。状態は repo のファイル（spec.md・tasks.md・qa.md・state.json）が正本で、"
          "会話の記憶に頼らず、下の状態から続ける。手順は /autopilot の command 本文、行き詰まりは references/dead-end.md。")
SHOWN = ("discovery", "building", "wait", "blocked", "queued")
RECORDED = ("building", "wait", "queued")
PAUSING = ("startup", "resume")  # セッションの外で止まっていた時間がある起動。compaction・clear は同じセッションの続き
OTHERS = ("spec-autopilot: このセッションが自走を引き受けていない spec がある（fork・同じ repo の別のセッションなど）。"
          "このセッションでは続けず、Stop hook も止めない。人がこのセッションで引き継ぐと言ったときだけ、"
          "先に autopilot.py adopt <dir> を実行してから /autopilot の手順で続ける。")
ADVISE = ("spec-autopilot の相談役の規則: 人に方向を決めてもらう返事待ち（選択肢を挙げた確認、1 つの案の承認待ち、"
          "確認点を挙げた返事待ち）で turn を終える前に、2 段で相談する。1 段目は spec-autopilot:fable-advisor を 1 本、"
          "材料を場所で渡して起動し、推奨を受け取る。2 段目は、その推奨の `推奨:`・`理由:`・`引いた決定:` の欄だけ"
          "（推論の過程・比較の軸は渡さない）と、依頼の原文と材料の場所を spec-autopilot:advice-checker に渡して 1 本起動し、"
          "根拠を repo の事実に当てて反証を探させる。`判定: 反証あり` なら、最初の材料の場所・最初の推奨・成り立たない主張を"
          "渡して 最初の推奨を出した相談役を 1 本起動し、1 回だけ推奨を直させ、検証はし直さない（段は 2 段で止める）。本文には、推奨、"
          "反証の判定と根拠、自分の案との食い違いを載せ、推奨を直したときは最初の推奨と並べて、直した推奨が検証されていないと書く。推奨の反証は main が自分でしない（main は並べた案の作り手で、自分の案に寄るため）。"
          "推奨が `引いた決定:` を持つとき、advice-checker がその主張を `成り立つ` としたならその検証で読み直しに代える。"
          "反証ありで直させた推奨と、`確かめられない` とされた主張は、main が引かれた行を読み直してから使う。"
          "advice-checker を回さなかった・起動できなかったときも、main が引いた行を読み直してから使う。"
          "fable-advisor か advice-checker を起動できないとき（再試行は 1 回まで）は、本文に `<agent>: unavailable（理由）` と書いて進む。"
          "2 段目を起動できなければ、推奨が検証されていないと書く。"
          "spec-autopilot:opus-advisor は、人が名指ししたときだけ起動する。名指しのときは opus-advisor を 1 段目にし、"
          "2 段目の advice-checker は同じく回し、反証ありの直しは最初の推奨を出した opus-advisor にさせる。"
          "1 つの確認に 1 回で、人の直しを受けた示し直しでは相談し直さない。除くのは、答えを人しか持たない事実の問い、"
          "決めることの無い報告、利用者の規則が 1 操作ごとに求める操作の許可（マージ・デプロイ・apply・破壊的な削除など）。"
          "repo の規則か手順（CLAUDE.md・/gdd-dev など）に別の相談の規定があれば、そちらに従う。")


def describe(autopilot, d, payload, own):
    """(このセッションが引き受けた spec か, 状態の文) を返す。知らせない spec は文が None。"""
    mine = False  # 場所が読めない spec は、引き受けていないものとして扱う（続ける指示を出さない）
    try:
        mine = d.resolve() in own
        phase = autopilot.load_state(d).get("phase")
        if phase not in SHOWN:
            return True, None
        if phase in RECORDED and not mine:  # 状態の行は指示を含むので出さない（場所と phase だけ）
            return False, f"{d}: phase={phase}。引き継ぐときだけ: autopilot.py adopt {d}"
        if phase in RECORDED and payload.get("source") in PAUSING:
            autopilot.pause_since_last_activity(d)
        report = d / "watch-report.md"  # 見回り役が起こせなかった理由
        return True, "\n".join(autopilot.status(d) + ([f"見回り役の報告: {report}（読んでから続ける）"] if report.exists() else []))
    except Exception as e:
        if not mine:
            return False, f"{d}: state.json が読めない（{type(e).__name__}）"
        return True, f"{d}: state.json か成果物が読めない（{type(e).__name__}）。直してから続ける"


def main():
    try:
        import autopilot
        import stop

        payload = json.loads(sys.stdin.buffer.read() or b"{}")
        unreadable = []
        own = {d.resolve() for d in stop.recorded(autopilot, payload, [])}
        found = [describe(autopilot, d, payload, own) for d in stop.candidates(autopilot, payload, unreadable)]
        try:  # 見回り役が host の生死を読む。書けなくても再開は止めない
            __import__("watch").record_host(payload)
        except Exception:
            pass
        mine = [p for ok, p in found if ok and p] + unreadable
        others = [p for ok, p in found if not ok and p]
        blocks = [ADVISE] + ([HEADER + "\n\n" + "\n\n".join(mine)] if mine else []) + (
            [OTHERS + "\n\n" + "\n\n".join(others)] if others else [])
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": "\n\n".join(blocks)}}
    except Exception as e:  # 再開を止めない
        out = {"systemMessage": f"spec-autopilot の SessionStart hook が状態を読めなかった（{type(e).__name__}）。autopilot.py status で確かめる",
               "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ADVISE}}
    print(json.dumps(out))  # ASCII だけにする
    return 0


if __name__ == "__main__":
    sys.exit(main())
