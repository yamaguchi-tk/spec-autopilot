# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_version_is_raised_past_0_1_12・::test_manifest_has_semver_and_name・::test_marketplace_entry_matches_manifest と cmd: .autopilot-qa/check.py で、base（76ea6de）の version 0.1.12 では足したテストの判定が落ち、tip では通ること、tip の version が 0.1.13 であること、marketplace.json の項目と name・description が一致すること、plugin.json は version 以外の欄が変わらず marketplace.json も変わっていないことを確かめた → R1 pass。回帰テストは 9 passed、全テストは 1263 passed。旧い値 0.1.12 を `git grep -l -F` で引くと、tests の中は 0 件（証拠: evidence/R1.txt） |
