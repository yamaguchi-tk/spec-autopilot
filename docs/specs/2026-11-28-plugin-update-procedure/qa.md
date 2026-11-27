# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: tip（4974e51）の CLAUDE.md:19 を `grep -n` で引き、`claude plugin update spec-autopilot@spec-autopilot`・`/reload-plugins`・`watch.py plist`・`--plugin-dir` の 4 語がすべて 19 行目にあり、`grep -c symlink CLAUDE.md` と `grep -c pull-checkout CLAUDE.md` はどちらも 0。変えない挙動の plugins/spec-autopilot/tests/test_ci_workflow.py は 6 passed（証拠は evidence/R1.txt） |
| R2 | pass | cmd: tip で `git grep -n pull-checkout -- ':(exclude)docs/specs' ':(exclude)docs/adr'` を回すと出力は 0 行（exit 1）、`test -e docs/pull-checkout.md` は 1 を返した（証拠は evidence/R2.txt） |
