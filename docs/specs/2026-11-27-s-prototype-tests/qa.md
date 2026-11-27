# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: autopilot-implementer.md の 2 の項を base（40e064c）と比べ、旧い文はそのまま残り（S でないときの書き方は変わらない）、後に足した文に、大きさ S のときだけ要件ごとに代表の 1〜2 件にすること・境界の値と表の値を期待値に入れること・再現テストと playbook のタスクが求めるテストと同時の書き込みのテストを数に数えないことがあると確かめた（evidence/R1.txt） |
| R2 | pass | plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body と cmd: 4 ファイルの 2 の項の shasum が 4 本とも同じだった（evidence/R2.txt） |
| R3 | pass | plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_version_is_raised_past_0_1_15・::test_marketplace_entry_matches_manifest と cmd: plugin.json の version が 0.1.16 で、回帰テストが 47 件通った（evidence/R3.txt） |
