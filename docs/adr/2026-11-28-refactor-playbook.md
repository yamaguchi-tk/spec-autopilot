# ADR: refactor の playbook を、測る道具の名前を書かずに足す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-refactor-playbook

## Context
リファクタの spec は playbook を `なし` で書き、合格基準を行数で書いていた。指標で測ると移しただけのリファクタが合格になった。測る道具は repo の外にあり、この repo は公開している。

## 選択肢
1. refactor.md を足し、測るコマンドを一般の語で書かせ、合格基準を前後の比べ方の形にさせる: 道具を持たない人も、自分の道具で同じ形に満たせる
2. refactor.md に手元の道具の名前とコマンドを書く: そのまま写せるが、道具は repo の外にあり、plugin を入れたほかの人の手元には無いので、書いたコマンドを回せない
3. playbook を足さず、/autopilot の本文にリファクタの書き方を足す: ファイルは増えないが、選んだ spec だけが読むという playbook の仕組みから外れる

## Decision
1 を選ぶ。

- 直し方: 入力の約束を変える
- 退けた: 要らなくする（今の手順では、リファクタの spec を `- playbook: なし` で書き、前の指標の値も前後の比べ方も求められない。2026-11-26-split-modules はそのまま行数の合格基準で、移しただけのリファクタを通した）

## Consequences
- refactor を選んだ spec は、前の値と前後の比べ方の合格基準を書く
- 手元の plugin を更新するまで、この repo の自走の lint は refactor を知らない
