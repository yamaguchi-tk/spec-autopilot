# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [ ] T1: scripts に evidence.py・size_note.py が無く、autopilot.py が `__import__("evidence")`・`__import__("size_note")` を持たず、`sys.modules[__name__]` を渡すのが premises と rootcause だけであることを確かめるテストを tests/test_import_layers.py に先に足して落ちることを確かめ、evidence.py の items と size_note.py の notes を autopilot.py のトップレベルの関数に移し、2 つのファイルを消す [R1, R2, R3]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる
