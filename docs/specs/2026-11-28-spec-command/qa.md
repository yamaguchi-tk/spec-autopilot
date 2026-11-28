# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | fail | 原因: 差分の外。入力: `claude -p --plugin-dir <worktree>/plugins/spec-autopilot --output-format stream-json --verbose -- "/spec 障害調査が賢くなるようにしたい"`（一時 repo は .autopilot-qa/tmp/vague/repo）。期待: 明示された依頼は CLI init・lint に進み、ふわっとした依頼は 4 項目と問い 1 つを返す。実際: 返事が "You've hit your weekly limit · resets Nov 29 at 9pm (Asia/Tokyo)" だけで、`--model sonnet` でも同じ。確かめを回せていない（init の event の slash_commands に `spec-autopilot:spec` が出ることだけは見た） |
| R2 | fail | 原因: 差分の外。R1 と同じ週の上限で、返事の時刻・tool の数・4 項目を確かめられていない。cmd: 前提「返事までの時間を stream-json の出力から読めるか」を .autopilot-qa/tmp/vague/out.jsonl の grep で確かめた → result の event に `duration_ms` がある（4856）。プロセスの起動から result までは 14.3 秒で、起動に約 9 秒かかる |
| R3 | fail | 原因: 差分の外。R2 の返事が得られず、具体例 2〜3 個を確かめられていない |
| R4 | fail | 原因: 差分の外。R2 のセッションが無いので「固めて」の tool の順を確かめられていない。別に、commands/spec.md が「## 0. 準備」を指していない high がある |
| R5 | fail | 原因: 差分の外。`/autopilot 障害調査が賢くなるようにしたい` の headless の実行も、同じ週の上限で回せていない |
| R6 | pass | plugins/spec-autopilot/tests/test_stages.py::test_lint_rejects_a_missing_doubled_unknown_or_unreadable_purpose_check・::test_lint_accepts_a_purpose_check_on_a_requirement_or_after_the_merge と cmd: 一時 repo で CLI init から CLI lint までを回した。R1 とマージ後は通り、行が無い・2 本・R9・制約の節にだけある・コメントの中にだけある・R10 は「目的の確かめ」の ERROR で rc=1 になった（evidence/R6.txt） |
