# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_advisor_approval.py::test_advice_checker_definition_gives_one_verdict_line_form_that_the_gate_accepts と cmd: 28 行目を base の `判定: 反証なし` に戻す patch（.autopilot-qa/mut-R1-1.patch）を当てると同じテストが `assert ['`判定: 反証なし'] == []` で落ち、出力の節の括弧を `（確かめられない <n>）` に変える patch（mut-R1-2.patch）でも読み出しの assert で落ち、どちらも git apply -R で戻した後の tip では通った（`approve --by-advisor` を CLI から打って phase が building。回帰テストと test_goal_child.py を合わせて 70 passed）（evidence/R1.txt） |
| R2 | pass | plugins/spec-autopilot/tests/test_advisor_approval.py::test_advice_checker_definition_gives_one_verdict_line_form_that_the_gate_accepts と cmd: tip の advice-checker.md:28 は「下の出力の形で `反証なし` と判定し」となっていて出力の節を指している。守ることの節を `` `判定: 反証 `` で grep すると 0 件（exit=1）。回帰テストは 47 passed（evidence/R2.txt） |
