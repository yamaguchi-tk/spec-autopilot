# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R1, R2]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1, R2]
  - メモ: state.json の existing を読む箇所は prototype_ok・lint・cmd_done の 3 つだけで、全部 is_new_repo に置き換え済み。agent_gate.py は prototype_ok を呼ぶだけで、ほかの scripts・hooks に別の読み方は無い。agents の文言は existing が false のときだけ新しく作る repo と書いてあり同じ向きなので変えない
