# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R2]
  - メモ: base で落ちることを確かめてから commit する
- [x] T2: 根本の原因を直す [R2]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R2]
  - メモ: autopilot.py の中で bounded の行に当てる正規表現（91〜95 行など）を測り、遅いものだけ直す
  - メモ: 当てない。TASK_NOTE・HEADING・QA_HEAD・QA_SEP・COMMENT・QA_ROW を、4,000 字までの行の最悪の形（字の連なり 13 通り × 頭 8 通り）で測ると、どれも 4,000〜16,000 字で 1 ms 前後の行の長さに比例する時間だった。遅い形は無いので直さず、test_each_line_regex_of_check_ends_in_linear_time_on_the_longest_lines で守る（旧 TASK に戻すと落ちる）
- [ ] T4: CI の workflow でテストの道具の版を固定して -n auto で回し、CLAUDE.md のテストの行を直す [R1, R4]
- [ ] T5: 照合役の定義に、回帰テストがテスト全体を回すなら ng にする文を足し、version を上げる [R3, R5]
