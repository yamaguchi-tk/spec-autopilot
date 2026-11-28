# ADR: 照合役も段ごとの定義で選び、setup の対話を 2 回の問いに分ける

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-role-model-setup-command

## Context
1 本目（docs/specs/2026-11-28-role-model-setup-advisors）が相談・検証の段を `ladder.py setup` に足す。人は相談役を含む全部の役の model と effort を setup で選べることを求めた。照合役も定義で model・effort を固定している。AskUserQuestion は 1 回に 4 問まで。

## 選択肢
1. 1 本目と同じく段ごとの定義を足し、1 本目の段の表に照合を足す（読み替えの行は表から作る）。command は 4 問と 1 問の 2 回に分ける: 仕組みが 1 つで済む
2. 照合役の段を spec の `## モデル` に写し、`overnight.py agent --role check` で名前を出す: spec ごとに変えられるが、並行の spec が直している commands/autopilot.md を変える

## Decision
1 を選ぶ。照合役も相談役と同じく 1 本目の表から作る読み替えの行で扱えば、autopilot.md を変えずに済む。

- 直し方: 設計を変える
- 退けた: 要らなくする（1 本目だけでは照合役の model・effort を変える道と、setup の対話が無い）
- 退けた: 入力の約束を変える（起動に model を渡す約束にすると、別名の解決と effort の固定ができない）

## Consequences
- 照合役を spec ごとには変えられない（手元の設定で全部の spec に効く）
