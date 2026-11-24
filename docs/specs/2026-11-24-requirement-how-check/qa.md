# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: handoff-after-close の spec.md を写した一時の repo で `claude -p --plugin-dir <worktree>/plugins/spec-autopilot --agent spec-autopilot:autopilot-spec-checker` を 2 回回した。2 回とも項目 10 に R1 の `ng` の行があり、最後の根拠の列に「prompt に書かれた」と「作り方の節へ移す」があった（例: `「prompt に書かれた」を作り方の節へ移す: spec.md:9`）。前の巡で見た、語が「確かめた方法」の列に入る揺れは、合意し直しの 2 回を足した 4 回のどれにも出なかった（evidence/R1.txt） |
| R2 | pass | cmd: handoff-after-close の 4 回（ふつうの照合 2 回と合意し直し 2 回）で、項目 10 が R8 を `ng` にした行は 0 本だった（out-h2 では R8 を「外から見える約束」として `ok`）。advise-stray-space を写して 2 回回すと、項目 10 は 2 回とも R1 の `ok` 1 行だけで、`ng` は 0 件だった（evidence/R2.txt） |
| R3 | pass | cmd: R1 と同じ一時の repo で、prompt に「合意し直し」を足して 2 回回した。2 回とも項目 1・2・3・4・6 が 1 行ずつ `該当なし（合意し直し）` で、まとめた行は無く、項目 10 に R1 の `ng` の行があり、根拠の列に「prompt に書かれた」と「作り方の節へ移す」があった。commands/autopilot.md:115 は「5・7・8・9・10」と書いている（evidence/R3.txt） |
| R4 | pass | plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_referenced_files_exist と cmd: plugin.json の version は 0.1.2、marketplace.json の description は plugin.json と同じ、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` は 6 passed。テストの置き場を旧い値 `0.1.1`・`根拠（path:line）` で git grep しても当たりは 0 件（`5・7・8・9` は新しい値の「5・7・8・9・10」にだけ当たる）。前の巡の結果のままで、evidence/R4.txt は書き直していない |
