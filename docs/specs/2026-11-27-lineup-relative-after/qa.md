# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_lineup.py::test_queue_writes_only_the_directory_name_of_the_dependency_to_state_json・::test_no_state_json_of_the_dependent_pair_holds_a_local_path_after_queue_start_and_end と cmd: 変異 mut-R1-1（enqueue の after を絶対パスに戻す）でこの 2 本の 3 件が落ちた |
| R2 | pass | plugins/spec-autopilot/tests/test_lineup.py::test_next_starts_a_dependent_spec_in_another_worktree_from_the_name_in_state_json・::test_next_still_reads_an_absolute_path_left_in_after_by_the_earlier_version・::test_next_starts_a_dependent_spec_after_cmd_done_dropped_its_dependency_from_the_record・::test_next_blocks_a_dependent_spec_after_cmd_block_dropped_its_dependency_from_the_record・::test_next_starts_a_dependent_spec_on_top_of_its_dependency |
| R3 | fail | cmd: 対のファイルか依る spec の state.json が壊れているとき、next は「記録に無いか 2 本以上」の理由で block にし、Stop hook は何も言わない |
