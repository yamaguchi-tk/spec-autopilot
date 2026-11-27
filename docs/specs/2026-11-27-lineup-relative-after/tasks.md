# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2, R3]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R1, R2, R3]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1]
  - メモ: 洗い出し: (1) `after` を読む・書く箇所は lineup.py だけ（scripts・hooks に他の読み手は無い）。(2) lineup.py が state.json に書くパスは `after` だけで、対は repo の外（SPEC_AUTOPILOT_HOME）。(3) state.json に絶対パスが入りうる別の箇所は overnight.py の `qa_runs`・`rolled_back` の `evidence`（呼び出し元が渡したパスをそのまま書く）。(3) は直さない: 観測した漏れは `after` だけ（git 履歴の state.json の絶対パスは全て `after`。今の docs/specs の state.json に evidence の絶対パスは無い）、この spec の影響範囲は lineup.py で、overnight.py の同じ値は重複の判定にも使う（変えると別の挙動になる）。必要なら別の Issue。両方の state.json に手元のパスが入らないことは test_no_state_json_of_the_dependent_pair_holds_a_local_path_after_queue_start_and_end で守る
- [x] T4: 依る spec が done・block で記録から外れた後も、enqueue で repo の外に書いた対から依る spec を引き、着手できるようにする（実物の cmd_done を通すテストで確かめる） [R2, R3]
  - メモ: 作り方はこの spec の ADR の「実装中に変えた決定」
- [x] T5: 対のファイルか依る spec の state.json が読めないときは、「対が無い」と区別し、読めないファイルと理由を next の block の理由に入れ、Stop hook は既にある読めないときの文で知らせる [R3]
  - メモ: 評価役の high（lineup.py の released の except が壊れを捨てている）
