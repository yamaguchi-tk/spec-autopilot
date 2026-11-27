# ADR: 大きさが L の NOTE を、done に加えて check --stage pr でも出す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-size-note-at-pr

## Context
「大きさが L になった」の NOTE は、PR を stacked PR に分けるかを決めるためのものだが、cmd_done だけが出す。範囲がマージ以上の spec は、PR を作ってマージした後に done にするので、NOTE が分ける段より後に出る。

## 選択肢
1. 大きさの判定を関数に切り出し、check の stage が pr のときにも出す: PR の前の検査で出る。done の NOTE も残る
2. done の NOTE を check --stage pr に移し、done からは消す: 範囲が「PR まで」の spec では done が PR の前なので、消すと今のテストの約束が変わる
3. 手順の文で、PR の前に `CLI size` を回すよう書く: 機械では出ず、手順の読み落としで同じ詰まりに戻る

## Decision
1 を選ぶ。autopilot.py は 1391 行で目安（1500 行）に近いので、判定は新しいファイルに移す。

## Consequences
- 範囲がマージ以上の spec でも、PR を作る前に分けるかを決められる
- 範囲が「PR まで」の spec では、check --stage pr と done の両方で同じ NOTE が出る
