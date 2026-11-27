# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [ ] T1: carry.py に、最後の dispatch を閉じた handoff の tip と今の HEAD で spec の置き場の外が同じかを見る判定を足し、lineup.py の begin が blocked の承認し直しでそれが成り立つときに dispatches と handoffs を残し、`引き継いだ: `・`dispatch を引き継がなかった: ` の行を出す。test_carry.py:76-85 と test_prototype_gate.py の after=blocked の dispatches・handoffs の期待を書き換え、文だけ・spec の外の変更・開いた dispatch の 3 つの場合のテストを足す [R1]
