# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: 変えた feature.md の 12 行目を読み、S の草案について「本体（テストと docs を除く、足す行）が 200 行に収まる」「12 個まで埋めず」「公式のルールや資料の細部は要件に入れず、非目標の『足すなら』に挙げる」「普通は付く機能は目安に収まる範囲で残す」の 4 つがあることを確かめた（evidence/R1.txt） |
| R2 | pass | cmd: 128f67b の照合役で、fixtures を spec.md として置いた一時の repo で `claude -p --plugin-dir <worktree>/plugins/spec-autopilot --agent spec-autopilot:autopilot-spec-checker` を回した。browser-tetris は 2 回とも項目 11 に ng があり（5 本と 4 本。根拠は「大きさを M にする」か「非目標へ移す」）、number-guess は項目 11 が ok の 1 行だった（見積もり 60〜105 行）（evidence/R2.txt） |
| R3 | pass | cmd: 128f67b の照合役で、browser-tetris の一時の repo で prompt に「合意し直し」を足して 2 回回した。2 回とも項目 1〜4・6 は 1 行ずつ `該当なし（合意し直し）` で、項目 11 に ng があった（5 本と 6 本）。照合役の定義の 9 行目と commands/autopilot.md:117 の見る項目に 11 が入っている（evidence/R3.txt） |
