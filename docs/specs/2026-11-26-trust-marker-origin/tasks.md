# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R1, R2]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1, R2]
  - メモ: 人の発言を origin で判定するのは human_said_at だけで、呼び出し元は approve（autopilot.py:971）と resume（1085）の require_user_after の 2 つ。どちらも直した require_user_after を通り、テストは approve・resume の両方で回している。trust を読むのも require_user_after だけ。stop.py と anomalies の transcript の走査は、人の発言の判定ではないので当てない
