# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: autopilot.py が lineup を import しないこと、after.py・building.py が lineup・overnight・autopilot・light を import しないこと、移した名前が after・building・autopilot に定義され lineup.py が import することを確かめるテストを tests/test_import_layers.py に先に足し、autopilot.py の import 先の数の期待を直して落ちることを確かめ、lineup.py の after_name・AFTER・NEXT・pairs_file・pairs を after.py に、autopilot.py の head_and_body・sha と lineup.py の begin を building.py に、lineup.py の queue_lint・enqueue・minutes（queue_minutes にする）・session_of・remember を autopilot.py に、中身を変えずに移す [R1, R2, R3, R4]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる。lineup.py で使わなくなる import（fcntl・json・carry・deploy など）は消す。lineup.py は pairs・after_name・begin・NEXT を import し直し、light.py:41・57 と test_lineup.py:486 が今の名前で読めるようにする。test_lineup.py:479 は呼ぶ先を autopilot.remember に向け直す（期待は変えない）
