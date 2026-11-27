# ADR: 評価役は、自分で起こした処理を kill・pkill でなく TaskStop で止める

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-denial-stop-reviewers

## Context
split-modules の夜の run で、実装役・評価役は自分で起こした処理を `pkill`・`kill` で止めようとし、権限の自動判定に 8 件拒まれた。定義の tools には TaskStop が無く、止め方は書かれていない。親の spec（2026-11-27-flow-review-goal）の R2 が、TaskStop で止めることを指示すると決めた。

## 選択肢
1. 定義の tools に TaskStop を足し、本文に「kill・pkill でなく TaskStop で止める」を書く
2. 本文に「処理を裏に回さない」とだけ書き、止める道具は足さない: 裏に回った処理（Bash の timeout で background に移ったものを含む）を止める手段が無いまま残る
3. 権限の許可を足して kill を通す: 人の設定を変えることになる

## Decision
1 を選ぶ。7 つの定義はファイルの数で 1 本の spec にすると大きさが L になるので、評価役の 3 つをこの spec にし、実装役の 4 つは 2026-11-28-denial-stop-implementers に分けた。

## Consequences
- 評価役が TaskStop を使えるようになる（実装役は 2026-11-28-denial-stop-implementers）
- 拒否の件数が減ったかは、この後の run の集計で確かめる
