# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | plugins/spec-autopilot/tests/test_prototype_gate.py::test_dispatch_in_discovery_accepts_a_small_spec_and_prints_the_implementer と cmd: base（e26a1cb9）の plugin を .autopilot-qa/base に展開して同じテストを回すと落ち、tip では終了コード 0・最後の行 autopilot-implementer・dispatches 1 件になった |
| R2 | fail | spec.md を読めない S の spec（chmod 0）の dispatch が、読めなかったことを出さずに phase の理由だけで拒む（is_small の except が S でないと区別なく返す） |
| R3 | pass | plugins/spec-autopilot/tests/test_prototype_gate.py::test_gate_allows_the_implementer_dispatched_in_discovery と cmd: base では同じテストが落ち、tip では hook の出力が空で終了コード 0 |
| R4 | fail | test_prototype_gate.py の deny のテストが `kind, _ = decision(...)` で受けるので、hook が通す変異で TypeError で落ち、assert で落ちない（変異が判定できない） |
| R5 | fail | discovery から --queue で承認した spec が着手で block され、approve し直すと begin(prev=blocked) が試作の dispatches を消し、handoff が「dispatch の記録が無い」で拒む |
| R6 | pass | cmd: small-prototype.md の 8 行目（起動の前に tasks.md を書いて dispatch する。discovery の S だけ）と 21 行目（[x] にして handoff で閉じる）、overnight.py の 5 行目の使い方、agent_gate.py の docstring の 3 行目に discovery の S があり、plugin.json の version は 0.1.3 |
