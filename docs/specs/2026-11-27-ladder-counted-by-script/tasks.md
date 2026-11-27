# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2, R3, R4, R5]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す（agent_gate の記録と deny、cmd_review の累計、ROUND_KEYS） [R1, R2, R3, R4, R5]
  - メモ: 否定された仮説から足したコードは戻す
  - メモ: T1 のテスト 1 件（dispatch を開いたまま review を記録する手順）は review_gate の上で成り立たないので、人の許しを得て hook の deny までに縮め、dispatch が断る流れのテストを足した。dispatch でも断るのは、hook の deny だけでは開いた dispatch の後に review を記録できず行き詰まるため
- [ ] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R3]
- [ ] T4: dead-end.md・autopilot.md・README.md・hooks.json の数え方の文と、autopilot.py の梯子の文を直す [R6]
