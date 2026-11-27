# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: consent.py に承認の中身のハッシュと記録・起点の関数を置き、`autopilot.py lint` の CLI が通ったときだけ state.json に記録し、approve（人の発言の門）の起点にする [R1, R2]
  - メモ: 起点は min(記録の時刻, spec.md の最後の変更) にした（人の発言の後に初めて lint しても、中身が同じなら今までどおり通る）。記録は discovery・blocked・done のときだけ書く。実装役はテストを実装の後に書いた（実装を壊して落ちることは確かめた）
- [ ] T2: `--by-advisor` の承認し直しと目的の spec の子の承認（goal.py の child_errors）の起点を T1 と同じにし、advisor_approval.py の文・commands/autopilot.md の起点の説明・test_goal_child.py の文を合わせる [R3]
