# QA の結果

<!-- 結果は pass / unverified / fail。pass の証拠は `<path>::<テスト名>`（pytest の node id `<path>::<クラス>::<テスト名>` も可。複数は `・` で並べ、同じファイルの続きは `::<テスト名>`。続けて ` と cmd: ...` を書ける。末尾の 1 組の（…）は注記）・`cmd: <実行したことと結果>`・`manual: <操作と結果>`。並べたテストが 1 つでも無ければ check が落ちる。spec の段が手元で実物の要件の pass は `evidence/R<n>.*` に、デプロイ後の pass は `evidence/R<n>.txt` に、`$ <コマンド>` の行とその出力を残す（デプロイ後はデプロイの後に書き、頭に `- commit: <マージの sha>` と `- 結果: Confirmed` を 1 本ずつ）。unverified は spec の `- unverified の承認:` か、その要件を積んだ park があるときだけ通る -->
| 要件 | 結果 | 証拠 |
|---|---|---|
| R1 | pass | cmd: 2 つのファイルの 8 行目（description）を `sed -n 8p` で読んで grep し、「レビュー指摘の直し方」「設計判断」が 0 件、「目的の spec の子の承認」「block の後の承認し直し」「IaC の初回の apply を含む spec」の 3 つがどちらのファイルでも当たった。`.autopilot-qa/check.py` でも、frontmatter の description 全体（`<example>` を含む）に禁止の 2 語が無く、名指しの括弧に 3 つの場面があることを確かめた（evidence/R1.txt） |
| R2 | pass | plugins/spec-autopilot/tests/test_advisors.py::test_agent_front_matter[fable-advisor-fable-medium]・::test_agent_front_matter[opus-advisor-opus-high] と cmd: `.autopilot-qa/check.py` で base d344a42 と比べた。名指しの括弧の中を同じ記号に置き換えると frontmatter が一致し、本文も一致した。`git diff --numstat` は plugins の 2 ファイルが 1 行ずつの変更だけで、回帰テストは 14 件すべて通った（evidence/R2.txt） |
