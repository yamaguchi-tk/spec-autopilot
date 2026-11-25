# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: overnight.py に入力の種類の表の検査を置き、dispatch・handoff・review_errors から呼び、dispatch の出力に表の渡し方を足す [R1, R2, R3, R5]
  - メモ: 前提: check の出力に R1 が出れば、R1 の入力の表の誤りが出たとみなせる → 崩れた（check は表と関係なく「最後のレビューに high（R1）が残っている」を出す。plugins/spec-autopilot/tests/test_input_kinds.py:182-184 の assert が変異 mut-R3-2 でも通った）。表の誤りの文そのもの（「R1 の入力の表」と「評価役を回し直」）で確かめる
- [x] T2: 評価役の 3 つの定義に表の書き方と書いてよい先の inputs/ を足し、version を 0.1.5 に上げる [R4, R6]
