# ADR: goal は、作業ツリーで done でない子を、子のブランチの done の state と gh で確かめたマージから done と読む

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-goal-reads-merged-child

## Context
範囲がマージ以上の子は、マージしてから done にし、done の state を子のブランチに commit する。main の作業ツリーにある子の state.json はマージの前のままなので、goal は子を done と読めない。

## 選択肢
1. 子のブランチの done の state を ref から読み、その最後のマージを gh で確かめる: 手順を変えずに読める。ブランチを消すと読めない
2. done の state の commit をマージの前に回す: done はマージの記録を求めるので、done の検査と手順の順を変える必要がある
3. 子ごとに、マージの後に done の state を main に入れる PR を作る: 子ごとに PR とマージが 1 本ずつ増える

## Decision
1 を選ぶ。ブランチの state は agent が書けるので、gh で、PR の番号が正の整数で、記録が戻しでなく、PR がマージ済みで、マージの commit が記録と同じで、base が既定のブランチで、head のブランチが done の state を読んだブランチと同じで、PR がその子のディレクトリを変えたことを確かめたときだけ done と読む。確かめられなければ作業ツリーの phase のまま読む。

## Consequences
- 子のブランチがローカルか remote-tracking に残っている間は、main の作業ツリーで goal が親を閉じられる
- goal が gh を呼ぶようになり、gh が使えない環境では今までどおり作業ツリーの phase で読む
