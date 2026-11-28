# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: light が輪に入らないこと、autopilot.py が light を import しないこと、light_rules.py が stages と deploy のほかに scripts を import しないことを確かめるテストを tests/test_import_layers.py に先に足し、輪の期待を 3 つに直して落ちることを確かめ、light.py の 30-149 を中身を変えずに light_rules.py に移し（`ap.` の名前は stages から import する）、light.py は EMPTY_TREE・command_errors・hits を light_rules から import し、autopilot.py の check は light_rules の errors を呼ぶ [R1, R2, R3, R4]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる。light.py で使わなくなる import（re・subprocess など）は消す
