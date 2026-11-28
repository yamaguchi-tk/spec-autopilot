# ADR: import の輪を、5 ファイル以内の子に分けて外側から切り、この子は補助を stages.py に移す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-deploy-stages

## Context
scripts の 8 モジュールが 1 つの import の輪になっている。輪の中のモジュールは autopilot.py の補助（文の読み取り・state・repo の場所）を借り、autopilot.py は CLI の入口として関数の中でそれらを import する。lint は 1 本の spec が 6 つ以上のコードのファイルを変えると L として止めるので、輪を 0 にする親の R4 は 1 本では合意できない。親の R5 は子ごとに指標の悪化を禁じ、autopilot.py の fan-out（16）と LCOM4（4）は目安の高を超えているので、1 でも増えれば悪化になる。

## 選択肢
1. 輪の外側のモジュールから順に、使う補助を下の層に移して直接 import させ、まだ向け直さないモジュールは autopilot.py を通して使い続けさせる。この子は補助を、autopilot.py と deploy.py がもう import している stages.py に移す: 5 ファイル以内に収まり、autopilot.py の fan-out が増えず、循環の組が減るので「移しただけ」にならない
2. 1 と同じ順で、補助を役ごとの新しいモジュール（spec の文の読み取りと、repo の場所）に出す: 役の名前はそろうが、autopilot.py の fan-out が 16 から 18 に増えて悪化になる
3. 下の層に出す名前を全部 1 本の子で移し、使うモジュールを全部同じ子で向け直す: 途中で autopilot.py を通す使い方が残らないが、20 近いファイルを変えるので L になり、lint が止める

## Decision
1 を選ぶ。この子は deploy.py と stages.py を外し、preflight.py も一緒に輪を出る。stages.py の LCOM4 は 1 から 2 になるが、目安（2 を超えたら警告）の内に収まる。autopilot.py の diff_size の中の関数は、補助を抜くと LCOM4 のつながりを失うので、トップレベルの関数にする。

- 直し方: 設計を変える
- 退けた: 要らなくする（移す補助は deploy.py・stages.py の判定がこれからも使う。消せない）
- 退けた: 入力の約束を変える（CLI の引数・spec の書式を変えても、モジュールの依存の向きは変わらない）

## Consequences
- この子の後も、goal・light・lineup・overnight・runlog・watch・hooks は、移した名前を autopilot.py を通して使う。後の子が向け直し、最後の子の後には残らない
- stages.py は、QA の段の判定と spec の文の読み取りの両方を持つ。後の子で fan-out に余裕ができたら、役ごとに分け直せる
- stages.py の関数の引数が 1 つ減る
