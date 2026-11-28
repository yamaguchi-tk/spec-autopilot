# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [ ] T1: deploy.py・stages.py が autopilot を import せず、stages.py の関数が autopilot を引数に受けず、spectext.py・repo.py が scripts のモジュールを import しないことを ast で確かめるテストを先に足して落ちることを確かめ、補助を spectext.py・repo.py に出して deploy.py・stages.py・autopilot.py を直接の import に替える [R1, R2, R3, R4]
  - メモ: 測る道具は利用者の skill の置き場の refactor-metrics にある。着手の commit を `--base` に渡して前後を比べる
