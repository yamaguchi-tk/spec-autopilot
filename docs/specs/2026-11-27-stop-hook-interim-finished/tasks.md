# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R1, R2]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1]
  - メモ: meta.json の finished を読むのは hooks/stop.py の _running だけ（grep で確認）。scripts/overnight.py の launches と scripts/advisor_approval.py の launches は agentType と transcript だけを読み finished を使わず、watch.py の quiet は transcript の mtime だけ、scripts/transcript.py の agents は run_in_background の起動を読むだけなので、同じ直しは当てない
- [ ] T4: plugin.json の version を 0.1.21 に上げ、版数のテストを 0.1.20 を超えたことを見るものに置き換える [R3]
