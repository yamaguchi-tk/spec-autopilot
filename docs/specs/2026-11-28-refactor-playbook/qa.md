# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_playbooks.py::test_lint_accepts_known_names_or_none_with_a_reason[refactor]::test_the_playbooks_are_the_files_in_the_folder と cmd: 一時の git repo で `- playbook: refactor` の spec に CLI lint を回すと rc=0 で playbook の ERROR は 0 行、綴りを違えた refactr は rc=1 で ERROR（evidence/R1.txt） |
| R2 | pass | cmd: commands/autopilot.md の索引の表に refactor の行がちょうど 1 行あり、選ぶときの文は「挙動を変えずに構造（結合度・凝集度・複雑さ）を直すリファクタ」（evidence/R2.txt） |
| R3 | pass | cmd: refactor.md の見出しが bug-fix.md と同じ 3 節で、前提の書き方・合格基準の形・「移しただけで複雑さが変わっていないか」の観点が要件の文のとおり。道具の名前と手元のパスの grep は 0 件（evidence/R3.txt） |
