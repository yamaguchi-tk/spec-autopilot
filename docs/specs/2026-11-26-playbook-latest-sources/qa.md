# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: external-service.md の「spec を書くとき」7〜12 行目を読んだ。使う機能ごとに公式の文書・変更の履歴（What's New・リリースノート・API の changelog）・事例を調べてから要件と前提を書く文があり、`- 前提: …（確認日 2026-11-26）` の例と `  - URL: https://…` の例、事例を `- 普通のやり方:` の出典に書く文もあることを .autopilot-qa/check.py で確かめた → R1 pass（evidence/R1.txt） |
| R2 | pass | cmd: iac.md の「spec を書くとき」12〜17 行目を読んだ。provider の CHANGELOG で入った版を調べ、repo が固定する版（`.terraform.lock.hcl` など）と比べて、確認日と URL の行つきで前提に残す文と例があることを .autopilot-qa/check.py で確かめた → R2 pass（evidence/R2.txt） |
| R3 | pass | plugins/spec-autopilot/tests/test_playbook_sources.py::test_the_premise_example_in_the_playbook_passes_lint と cmd: `autopilot.py init` で作った一時の spec の「## 前提」に 2 つの例を写して `autopilot.py lint` を回した → どちらも rc=0 で ERROR は無し。対照として URL の行の後ろに文字を足すと rc=1 で「前提の行の形が読めない」になった（evidence/R3.txt） |
| R4 | pass | cmd: 2 つの playbook に足した箇条を読み、どちらにも「利用者の手元に最新を調べる skill があれば、それに従ってよい」があり、skill の名前（backtick・`/name`・`plugin:skill` の形）が無いことを .autopilot-qa/check.py で確かめた → R4 pass（evidence/R4.txt） |
| R5 | pass | plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_marketplace_entry_matches_manifest と cmd: plugin.json の version が 0.1.12（0.1.11 より上）であることを確かめ、回帰テストと test_playbook_sources.py を回した → 28 passed。旧い値 0.1.11 を `git grep -F` で引いたが tests には当たらなかった（evidence/R5.txt） |
