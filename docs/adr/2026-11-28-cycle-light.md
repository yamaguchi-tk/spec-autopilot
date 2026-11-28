# ADR: light.py の保護 path と自走の範囲の判定を下の層の light_rules.py に出し、light.py を入口だけにする

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-light

## Context
import の輪は autopilot・light・lineup・overnight の 4 つで残る。autopilot.py は check の中で light.errors だけを呼び、light.py の cmd_approve は autopilot.py の lint・take_over などを呼ぶので輪になる。親の spec は、light・lineup・overnight を autopilot.py の上に立つ CLI の入口として扱い、autopilot.py はほかの入口を import しないと決めた。light.errors とそれが呼ぶ判定（light.py:30-149）は、stages.py の名前と deploy.py だけを使う。

## 選択肢
1. light.py:30-149 を新しい下の層のモジュール light_rules.py に移す: autopilot.py は light_rules を呼び、light.py は入口だけになる。移した先は 1 つの判定の塊で LCOM4 は 1。autopilot.py の import 先の数は変わらない
2. light.errors とその判定を autopilot.py に移す: 新しいモジュールは要らないが、autopilot.py が約 120 行増えて 1,400 行を超え、凝集度の違う判定が入って R3 の子の仕事が増える
3. 既にある deploy.py に移す: deploy.py は自走の範囲の節を読むので近いが、deploy.py の LCOM4（5）が上がって悪化になる

## Decision
1 を選ぶ。中身は変えずに移し、`ap.` の名前は stages から直接 import する。light.py は cmd_approve が使う名前だけを light_rules から import する。

- 直し方: 設計を変える
- 退けた: 要らなくする（保護 path の判定は check と軽量フローの承認がこれからも使う。消せない）
- 退けた: 入力の約束を変える（spec の書式や保護 path の設定の形を変えても、check が判定を呼ぶ依存は残る）

## Consequences
- light.py は cmd_approve と main だけになり、autopilot.py・lineup.py・light_rules.py を import する入口になる
- 輪は autopilot・lineup・overnight の 3 つで、後の子で lineup・overnight を同じ形で外す
