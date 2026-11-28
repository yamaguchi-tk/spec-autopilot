# ADR: import の輪を、5 ファイル以内の子に分けて、下の層に補助を出しながら外側から切る

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-deploy-stages

## Context
scripts の 8 モジュールが 1 つの import の輪になっている。輪の中のモジュールは autopilot.py の補助（文の読み取り・state・repo の場所）を借り、autopilot.py は CLI の入口として関数の中でそれらを import する。lint は 1 本の spec が 6 つ以上のコードのファイルを変えると L として止めるので、輪を 0 にする親の R4 は 1 本では合意できない。移した名前を使うモジュールを全部同時に向け直すと 6 ファイルを超える。

## 選択肢
1. 輪の外側のモジュールから順に、使う補助を下の層に出して直接 import させ、まだ向け直さないモジュールは autopilot.py を通して使い続けさせる。子ごとに輪が縮み、最後の子で autopilot.py を通す使い方を無くす: 子ごとに 5 ファイル以内に収まり、子ごとに循環の組が減るので「移しただけ」にならない
2. 下の層に出す名前を全部 1 本の子で移し、使うモジュールを全部同じ子で向け直す: 途中の出し直しが無いが、20 近いファイルを変えるので L になり、lint が止める
3. autopilot.py を分けずに、輪の中のモジュールが autopilot の補助を引数で受ける形にする: ファイルは増えないが、親の R4 が禁じる、依存を道具から隠す形になる

## Decision
1 を選ぶ。この子は deploy.py と stages.py を外し、preflight.py も一緒に輪を出る。下の層は役ごとに spectext.py と repo.py に分け、LCOM4 を 2 以下に保つ。

- 直し方: 設計を変える
- 退けた: 要らなくする（autopilot.py の補助は deploy.py・stages.py の判定がこれからも使う。消せない）
- 退けた: 入力の約束を変える（CLI の引数・spec の書式を変えても、モジュールの依存の向きは変わらない）

## Consequences
- この子の後も、goal・light・lineup・overnight・runlog・watch・hooks は、移した名前を autopilot.py を通して使う。後の子が向け直し、最後の子の後には残らない
- stages.py の関数の引数が 1 つ減る
