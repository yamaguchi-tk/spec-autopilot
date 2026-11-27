# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: merged_child.py に子のブランチの done の state を ref から探して gh でマージを確かめる関数を置き、goal.py の cover が作業ツリーで done でない子に当てて、表の行に読んだブランチと PR を出す。test_goal_merged.py に、両方マージ済み・未マージ・マージの commit 違い・子のディレクトリを変えていない PR・base が既定のブランチでない PR・head のブランチが読んだブランチと違う PR・整数でない PR の番号・rollback の記録・gh の失敗の場合のテストを足す [R1]
- [x] T2: merged_child.py で gh の呼び出しが失敗したとき（exit 0 以外・JSON でない答え・タイムアウト・起動できない）、None を返す挙動は残し、子の名前・PR の番号・失敗の種類を stderr に 1 行出す。git show で ref にファイルが無いときは出さない。既定のブランチは read の中で 1 回だけ引く。テストを足す [R1]
  - メモ: 評価役の low（git for-each-ref の失敗を黙って None にする）は、壊れた ref でも exit 0 で失敗が再現しないので直さない
