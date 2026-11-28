"""CLI の出力（report）と、受けない phase の拒否（refuse）。stages.py のほかの scripts を import しない下の層。"""
import sys


def report(errors, extra, ok_message):
    for e in errors:
        print(f"ERROR: {e}")
    for w in extra:
        print(f"NOTE: {w}")
    if not errors:
        print(ok_message)
    return 1 if errors else 0


AFTER_DONE = ("done の後は Stop hook が止めないので、確認は wait を使わずにそのまま人に聞く。"
              "人に直しを頼まれたら、spec を直さずに済むなら tasks.md に直しのタスクを足して "
              "autopilot.py approve <dir> --by <返事の要約> で自走に戻る（spec を直すなら /autopilot の「done の後に直しを頼まれたとき」の手順に従う）")


def refuse(s, what):
    """受けない phase のときに止める。done なら、done の後の道（approve で戻る・そのまま聞く）を示す。"""
    if s.get("phase") == "done":
        sys.exit(f"{what}（phase=done）。{AFTER_DONE}")
    sys.exit(f"{what}（phase={s.get('phase')}）")
