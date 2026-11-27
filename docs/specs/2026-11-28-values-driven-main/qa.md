# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_advisor_rule_reads_values_first_and_proceeds_when_one_option_is_left と cmd: python3 .autopilot-qa/check.py で、hook の ADVISE と autopilot.md の A の 4・C の冒頭・人に戻るときに価値観を先に読む手順・反する案を並べない文・`- 価値観で退けた:` の行・数合わせをしない文があり、rootcause.check がその行を数えないことを確かめた（evidence/R1.txt） |
| R2 | pass | plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_advisor_rule_reads_values_first_and_proceeds_when_one_option_is_left と cmd: python3 .autopilot-qa/check.py で、残る案が 1 つなら問わずに進み理由を残す文を確かめた（evidence/R2.txt） |
| R3 | pass | plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_advisor_rule_asks_the_human_only_about_facts_permissions_and_purpose_changes と cmd: python3 .autopilot-qa/check.py で、hook の出力と autopilot.md が (a)(b)(c) の 3 つだけを問い、同じで反証なしなら進み、違えば自走中は park・自走していないときは人に問うと書き、食い違わないことを確かめた（evidence/R3.txt） |
| R4 | pass | plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_advisor_rule_makes_the_advisor_check_the_option_main_chose_not_choose_for_main・::test_session_start_gives_the_advisor_rule_outside_any_spec と cmd: python3 .autopilot-qa/check.py で、ADVISE・fable-advisor.md・README が相談役を main の案を確かめる役として書き、回帰テスト 580 passed（evidence/R4.txt） |
