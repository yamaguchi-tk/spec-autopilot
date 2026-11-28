# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [ ] T1: runlog.py が autopilot を import せず、runlog が輪の外にあり、stages.py の repo_root と git_lines が同じ関数で git を呼ぶことを確かめるテストを tests/test_import_layers.py に先に足して落ちることを確かめ、stated_size と SIZE_LINE・SIZE_ANY を stages.py に移し、git の呼び出しを 1 つの関数にまとめ、runlog.py を stages の import に替える [R1, R2, R3, R4]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる
