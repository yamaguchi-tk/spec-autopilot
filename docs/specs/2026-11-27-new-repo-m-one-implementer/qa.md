# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: python3 .autopilot-qa/check.py で、autopilot-implementer.md の 2 の項を base d2ea963e と比べた。絞る条件が「大きさ S か、state.json の `existing` が false の M」になり、数えないテスト 3 種の文と「それ以外の spec（既存の repo の M 以上など）のテストの書き方は変えない」が残り、2 の項の前半とほかの行は base と同じだった → R1 pass（evidence/R1.txt） |
| R2 | pass | cmd: python3 .autopilot-qa/check.py で、autopilot-implementer.md の 2 の項に「どの大きさでも、ヘッドレスのブラウザを動かす自前の検査スクリプトは書かない（ブラウザの確かめは評価役が行う…」と「spec の QA の方向性が repo に足すよう求める E2E のテストは、この数に入れずに書く」があることを確かめた → R2 pass（evidence/R2.txt） |
| R3 | pass | plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body と cmd: python3 .autopilot-qa/check.py で、opus・opus-xhigh・fable の本文（frontmatter を除く）が既定の実装役と一致することを確かめた → R3 pass。回帰テストは 158 passed、テストの全量は 1425 passed（evidence/R3.txt） |
| R4 | pass | cmd: python3 .autopilot-qa/check.py で、autopilot.md を base と比べた。変わった行は 53・66・89・90 だけで、行の数は変わらない。M の行に「新しく作る repo は、全要件を受け持つタスク 1 つを implementer 1 本で」、B の 1 に「S と新しく作る repo の M は E2E のテストを repo に足さず…既存の repo の M 以上は…Playwright の E2E」、C の 1 にタスク 1 つ（playbook のタスクは先頭に残す）、C の 2 に「既存の repo の M 以上はタスクごとに 1 本」が書かれていた → R4 pass（evidence/R4.txt） |
