# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2, R3, R4, R5]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す（agent_gate の記録と deny、cmd_review の累計、ROUND_KEYS） [R1, R2, R3, R4, R5]
  - メモ: 否定された仮説から足したコードは戻す
  - メモ: T1 のテスト 1 件（dispatch を開いたまま review を記録する手順）は review_gate の上で成り立たないので、人の許しを得て hook の deny までに縮め、dispatch が断る流れのテストを足した。dispatch でも断るのは、hook の deny だけでは開いた dispatch の後に review を記録できず行き詰まるため
  - メモ: 前提: agent_gate が評価役の起動を記録する条件（dispatch が無いか、最後の dispatch が handoff で閉じている）は、review が記録を受ける条件と同じ → 崩れた（plugins/spec-autopilot/scripts/overnight.py:637-647 の review_gate は、今の HEAD で最後の dispatch を閉じた handoff と、commit していないコードが無いことを求め、dispatch の無い spec を断る）
  - メモ: 前提: review を記録できる状態で評価役の起動を記録すれば、記録の抜けを review の記録で解ける → 成り立つ（review を記録すると unrecorded_review が None になる。plugins/spec-autopilot/scripts/ladder.py の unrecorded_review）
  - メモ: 根本の原因は、review を受ける条件を hook が写して別に書いたこと。hook は overnight.review_gate をそのまま呼び、通るときだけ記録する
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R3]
  - メモ: streak を書く箇所は cmd_review（直した）、cmd_rework の 0 戻し（要件どおり残す）、lineup.py:81・89 の承認し直し（reviews と同じく新しい巡に入るので 0 でよい）の 3 つだけで、読む箇所（ladder_errors・status・cmd_rework の前提・raise_reason）は値を比べるだけで巡を数え直さない。fails・raises を読む overnight.py の impl_name と autopilot.py の raise_impl は、巡の数ではなく「失敗の記録の時刻」を見るので R3 の累計と食い違わない。よって追加の直しは無し（文言だけ T4 で直した）
- [x] T4: dead-end.md・autopilot.md・README.md・hooks.json の数え方の文と、autopilot.py の梯子の文を直す [R6]
- [x] T5: review を記録できない状態の評価役の起動を deny にし、複数の spec と書けないときの扱いと文書を合わせる [R1, R6, R7]
