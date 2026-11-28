# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: goal.py が輪に入らず autopilot を import しないこと、state.py・out.py・session.py が stages のほかに scripts を import しないことを確かめるテストを tests/test_import_layers.py に先に足し、輪と import 先の数の期待を新しい値に直して落ちることを確かめ、load_state・save_state を state.py に、report・refuse・AFTER_DONE を out.py に、session_file・recorded_specs・release を session.py に中身を変えずに移し、autopilot.py はそこから import し、goal.py の `ap.` を移した先と stages に向け直す [R1, R2, R3, R4]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる
  - メモ: goal.py の child_errors は引数名が `session`（goal.py:93）なので、`import session` の形にするとモジュールが関数の中で隠れる。`from session import release` の形で import する。watch.py も移す名前を autopilot 経由で使うので、tests/test_watch.py も回す
