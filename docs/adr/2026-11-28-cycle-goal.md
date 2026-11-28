# ADR: goal.py が autopilot.py から借りる補助を、役ごとの 3 つの下の層のモジュールに出す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-goal

## Context
import の輪は autopilot・goal・light・lineup・overnight の 5 つで残る。goal.py が autopilot.py から借りるのは、state.json の読み書き（load_state・save_state）、出力（report・refuse）、セッションの記録（release）と、stages.py にもう有る名前だけ。この補助は互いにほとんど呼び合わない。親の R5 は、R4 の子に限って autopilot.py の LCOM4 と fan-out の悪化を数えない。

## 選択肢
1. 役ごとに 3 つのモジュール（state.py・out.py・session.py）に出す: どれも LCOM4 が 2 以下。autopilot.py の import 先は 3 つ増える（親の R5 のただし書きで数えない）
2. 1 つのモジュールにまとめる: 新しいモジュールは 1 つで済むが、互いに呼び合わない補助が並び、LCOM4 が 4 以上で悪化になる
3. stages.py に寄せる: 新しいモジュールは要らないが、stages.py の LCOM4（2）が上がって悪化になる

## Decision
1 を選ぶ。中身は変えずに移し、autopilot.py は移した名前を import して今の名前のまま使う。goal.py は autopilot.py を import せず、移した先と stages.py を直接 import する。ほかのモジュールの向け直しは後の子で行う。

- 直し方: 設計を変える
- 退けた: 要らなくする（goal は state.json・出力・セッションの記録を使い続ける。消せない）
- 退けた: 入力の約束を変える（goal の CLI の引数や state.json の形を変えても、補助を呼ぶ依存は残る）

## Consequences
- autopilot.py の import 先は 15 から 18 に、LCOM4 は 4 から 8 になる（写しで測った値。R3 の子で塊ごとに分けて直す）
- 移した名前は、light・lineup・overnight・watch・hooks から autopilot.py を通して使われ続ける（出し直し）。0 件にするのは R4 の最後の子
