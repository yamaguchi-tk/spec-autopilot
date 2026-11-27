# ADR: 承認し直しで、最後の dispatch が閉じていて spec の外が同じなら、dispatch と handoff を持ち越す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-reapproval-carry-dispatch

## Context
reapproval-carry-merge は、承認し直しでマージとデプロイの記録を持ち越し、dispatch と handoff は新しい巡で数え直すと決めた。数え直すと、spec の文だけを直した承認し直しでは実装役に作るものが無く、handoff が「commit が無い」で止まる。戻す手順（`git restore --source=<base>`）は auto mode に拒まれ、人の手が要った。

## 選択肢
1. 最後の dispatch を閉じた handoff の tip と今の HEAD で spec の置き場の外が同じなら、dispatches と handoffs を持ち越す: carry.py の照合と同じ形で、閉じた記録をそのまま使う。spec の外が違えば今までどおり
2. 承認し直しの後、commit の無い handoff を許す: handoff の「commit が増えたか」の検査を緩める。実装役の報告を信じない、という handoff の目的を弱める
3. 戻す手順を残し、auto mode の許可を人に頼む: 毎回人の手が要る

## Decision
1 を選ぶ。持ち越すのは、最後の dispatch が handoff で閉じている場合だけにする（開いたままの dispatch は、実装役が何を作ったか分からないので持ち越さない）。前の phase が blocked のときだけ持ち越す（マージの持ち越しと同じ範囲）。

## Consequences
- spec の文だけを直した承認し直しは、handoff を打ち直して評価役へ進める
- 前の巡の dispatch の記録は history にも残る（数え方は今までどおり）
- 子 2 で、/autopilot の手順に「`dispatch を引き継いだ: ` の行が出たら dispatch を打たない」を書く
