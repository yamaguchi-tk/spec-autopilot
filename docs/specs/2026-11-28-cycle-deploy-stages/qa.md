# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_import_layers.py::test_deploy_preflight_and_stages_are_outside_the_import_cycle と cmd: 指標の道具を `--base df338ab` で回し、循環の組が 28 → 15、cycles が autopilot・goal・light・lineup・overnight・runlog の 1 つだけで、deploy・preflight・stages が入らない（evidence/R1.txt） |
| R2 | pass | plugins/spec-autopilot/tests/test_import_layers.py::test_deploy_and_stages_do_not_import_autopilot_even_inside_functions::test_deploy_and_stages_have_no_autopilot_reference_or_sys_modules::test_stages_functions_take_no_module_and_nobody_passes_one と cmd: deploy.py・stages.py の文字列とコメントの外に autopilot の import・参照・importlib・sys.modules・__import__ が 0 件で、stages の関数の呼び出し 9 か所はモジュールを渡さない（evidence/R2.txt） |
| R3 | pass | plugins/spec-autopilot/tests/test_import_layers.py::test_stages_imports_only_carry_among_scripts と cmd: stages.py が import する scripts は carry だけで、stages.py の LCOM4 2、autopilot.py の fan-out 16・LCOM4 4（evidence/R3.txt） |
| R4 | pass | plugins/spec-autopilot/tests/test_import_layers.py::test_autopilot_uses_stages_for_the_moved_helpers と cmd: 着手の commit と tip の scripts で lint・check・check --stage pr・status を 4 本の spec に回し、16 本とも終了コード・stdout・stderr が同じ。指標の前後の比べ方は悪化 0・改善 3 で、移しただけではない。回帰テストと足したテストは 925 passed（全量は CI。evidence/R4.txt） |
