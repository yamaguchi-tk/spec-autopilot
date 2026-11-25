# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2, R3, R4, R5]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R1, R2, R3, R4, R5, R6]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1]
  - メモ: building だけを受ける他の箇所を全部見て、当てない。dispatch と agent_gate だけが「承認の前に実装役を起動する」入口で、そこに当てた。overnight の await・handoff・merged・qa・rolled-back・park・lens、autopilot の wait・building_state・pause_since_last_activity、lineup の hold は、PR・マージ・QA・予算など承認の後の段のもので、試作には要らない。handoff は承認で dispatch を持ち越した後（building）に閉じる設計（R5）なので、discovery では受けない。stop hook・watch・session_start の building 判定は、自走中の spec の見回りで、試作は discovery のままなので対象外。
