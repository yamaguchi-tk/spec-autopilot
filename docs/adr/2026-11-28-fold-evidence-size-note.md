# ADR: autopilot.py だけが使う evidence.py と size_note.py を autopilot.py に戻し、import 先の余地を作る

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-fold-evidence-size-note

## Context
import の輪は 2 本目の子の後に 5 モジュール（autopilot・goal・light・lineup・overnight）になった。残りの 4 つが借りる state.json の読み書き・セッションの記録・出力の補助を下の層に出すと、autopilot.py が import するモジュールが増える。autopilot.py の import 先は 16 で、親の R5 は子ごとに指標の悪化を禁じるので、増やせる余地が無い。evidence.py と size_note.py は、autopilot.py の行の予算のために分けた部品で、autopilot.py のほかに使う側が無い。size_note.py は autopilot.py のモジュールごとを引数に受け、親の R4 が禁じる形になっている。

## 選択肢
1. evidence.py と size_note.py を autopilot.py に戻す: import 先が 14 になり、size_note.py の `sys.modules[__name__]` の 2 か所も無くなる。autopilot.py は約 35 行増えて 1,400 行に届かない。変えるファイルは 3
2. 2 つを戻さず、後の子で足す下の層のモジュールに、既にある部品（playbooks.py など）をまとめる: 戻すファイルは無いが、役の違う部品が 1 つのモジュールに入り、そのモジュールの LCOM4 が上がる
3. 後の子で足す補助を全部 1 つの新しいモジュールにまとめ、import 先を 17 にしない範囲に抑える: 新しいモジュールは 1 つで済むが、互いに呼び合わない補助が並ぶので LCOM4 が目安を超える

## Decision
1 を選ぶ。戻す関数は、autopilot.py の中で名前が重ならないトップレベルの関数にし、モジュールや正規表現を引数に受けず、同じモジュールの名前を直接使う。

- 直し方: 設計を変える
- 退けた: 要らなくする（大きさ L の NOTE と証拠の欄の区切りは、check と done がこれからも使う。消せない）
- 退けた: 入力の約束を変える（qa.md の証拠の書式や spec の大きさの行を変えても、2 つの部品を呼ぶ依存は残る）

## Consequences
- autopilot.py の import 先は 14 になり、後の子は下の層のモジュールを 2 つまで足しても 16 を超えない
- autopilot.py は行の予算（1,500 行）に近づく。後の子で補助を下の層に出すと、また減る
