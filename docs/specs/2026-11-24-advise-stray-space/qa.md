# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_advisor_rule_has_no_stray_space_after_watashite・::test_session_start_gives_only_the_advisor_rule_without_active_specs と cmd: session_start.py に startup・resume・compact・clear の SessionStart payload を渡して起動した。4 回とも rc=0 で、stdout は ASCII の JSON、systemMessage は無かった。additionalContext は「渡して最初の推奨を出した相談役を 1 本起動し」を含み、「渡して 最初」を含まなかった（証拠は evidence/R1.txt。回帰テストは 21 passed） |
