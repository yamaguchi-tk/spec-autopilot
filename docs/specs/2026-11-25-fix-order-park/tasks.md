# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: rootcause.py に段の並びと ADR の行の検査を置き、rework から呼び、park のコマンドを出す [R1, R2, R7]
  - メモ: 前提: 理由が全部 parked に入れば、コマンドは要件ごとに 1 本にまとめてよい → 崩れた（spec.md の R2 は「行ごとに、その要件を積む park のコマンドを出す」）
  - メモ: 前提: park は (kind, op, req, merges) が同じものを重複として捨てる → 成り立つ（plugins/spec-autopilot/scripts/overnight.py:1016-1019）。行ごとに --op を変えれば、行ごとのコマンドのまま全部が積まれる
- [x] T2: check が park に積んだ要件に作り直しと block を求めないようにし、承認の後の変更のエラー文を直す [R3, R4, R7]
- [x] T3: dead-end.md と adr-template.md に段と行の書き方を書き、rework の出力に前提のメモを残すと足し、version を 0.1.4 に上げる [R5, R6]
