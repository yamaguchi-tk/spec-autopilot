# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [ ] T1: carry.py に、最後の dispatch を閉じた handoff の tip と今の HEAD で spec の置き場の外が同じかを見る判定を足し、lineup.py の begin が blocked の承認し直しでそれが成り立つときに dispatches と handoffs を残し、`dispatch を引き継いだ: `（次の一手つき）・`dispatch を引き継がなかった: `（dispatch が無い場合も）の行を出す。test_carry.py:76-85 と test_prototype_gate.py の after=blocked の dispatches・handoffs の期待を書き換え、文だけ・spec の外の変更・開いた dispatch・dispatch の無い spec・`--queue` からの `lineup.py next` の 5 つの場合のテストを足す [R1]
