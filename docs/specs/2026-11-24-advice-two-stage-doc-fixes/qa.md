# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: advice-checker.md の 28・34・35 行目を読み、判定の行が `反証あり` / `反証なし` に続けて `（確かめられない <n> / <主張の数>）` を書く形になっていること、`反証なし` のときも `主張ごとの結果:` を書くこと、「とだけ判定する」が残っていないことを check.py で確かめた。R1 pass |
| R2 | pass | cmd: advice-checker.md の 8 行目の description に、入口として SessionStart・/autopilot の手順・利用する repo の規則があり、1 段目として fable-advisor と、人が名指ししたときの opus-advisor の両方があることを check.py で確かめた。R2 pass |
| R3 | pass | cmd: python3 .autopilot-qa/check.py && python3 -m pytest plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_autopilot.py -q -k "advis or session_start" を回し直した。R3 pass、20 passed |
| R4 | pass | cmd: session_start.py に `{"source":"clear","cwd":"<worktree>/.autopilot-qa/empty"}` を渡して起動した。出力は ASCII の JSON で、additionalContext に `<agent>: unavailable（理由）` の書き方と「2 段目を起動できなければ、推奨が検証されていないと書く」の文があった（check.py の R4 pass） |
| R5 | pass | cmd: 同じく session_start.py を起動した。additionalContext に「名指しのときは opus-advisor を 1 段目にし、2 段目の advice-checker は同じく回し、反証ありの直しは最初の推奨を出した opus-advisor にさせる」の文があった（check.py の R5 pass） |
