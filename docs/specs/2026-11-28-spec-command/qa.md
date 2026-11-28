# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | unverified | park: 週の利用上限で headless の claude が返事を返さない（11/29 21:00 JST の後に確かめ直す）。入力: `python3 .autopilot-qa/check.py drive`（`claude -p --plugin-dir <worktree>/plugins/spec-autopilot --output-format stream-json --verbose -- "/spec 障害調査が賢くなるようにしたい"` を一時 repo .autopilot-qa/tmp/vague/repo で回す）。期待: 明示された依頼は CLI init・lint に進み、ふわっとした依頼は 4 項目と問い 1 つを返す。実際: rc=1、返事は "You've hit your weekly limit · resets 9pm (Asia/Tokyo)" だけ、tools=[]。init の event の slash_commands に `spec-autopilot:spec` は出る |
| R2 | unverified | park: 週の利用上限で headless の claude が返事を返さない（11/29 21:00 JST の後に確かめ直す）。R1 と同じ上限で、返事の時刻・tool の数・4 項目を確かめられていない。cmd: 前提「返事までの時間を stream-json の出力から読めるか」を result の event で確かめた → `duration_ms` がある（2906）。起動から result まで 14.0 秒 |
| R3 | unverified | park: 週の利用上限で headless の claude が返事を返さない（11/29 21:00 JST の後に確かめ直す）。R2 の返事が得られず、具体例 2〜3 個を確かめられていない |
| R4 | unverified | park: 週の利用上限で headless の claude が返事を返さない（11/29 21:00 JST の後に確かめ直す）。R2 のセッションが無いので、「固めて」の後の tool の順を確かめられていない |
| R5 | unverified | park: 週の利用上限で headless の claude が返事を返さない（11/29 21:00 JST の後に確かめ直す）。`/autopilot` の headless の起動も、同じ上限で回せない |
| R6 | pass | plugins/spec-autopilot/tests/test_stages.py::test_lint_rejects_a_missing_doubled_unknown_or_unreadable_purpose_check・::test_lint_accepts_a_purpose_check_on_a_requirement_or_after_the_merge と cmd: 一時 repo で CLI init → spec.md を差し替え → CLI lint を回した。R1 とマージ後の行は rc=0、行が無い・2 本・R9・R10・マージ後（）・形が違う・制約の節にだけある・コメントの中にだけある、はどれも「目的の確かめ」の ERROR で rc=1。変異（要件に無い R<n> の ERROR を外す）でテストが落ちた（evidence/R6.txt、commit ed18f3e） |
