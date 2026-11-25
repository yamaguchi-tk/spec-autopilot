# qa.md の証拠のテスト名の中の `・`・`、` を区切りと読まない

- ADR: docs/adr/2026-11-25-evidence-split-before-a-file.md

## 目的
`autopilot.py check` は、qa.md の pass の証拠に並べたテストの名前の中に `・`・`、` があり、その後ろに `::<名前>` が続くと（jest の `describe` の名前など）、名前の後半を path と読み、「並べたテストが無い」で落とす（2026-11-24 の試走で、テスト名を直すタスクが 1 往復増えた）。評価役が書いた証拠をそのまま通し、テスト名を check に合わせて直す往復を無くす。できあがったら、名前に区切りの記号を含むテストを証拠に書いても check が通り、今の `・` での並べ方と `::` の続きの書き方は今までどおり読める。

## 要件
- R1: qa.md の pass の証拠に `<path>::<名前>::<名前>` の形でテストを書き、`::` の前の名前が `・`・`、`・`,` を含み、名前がどれも path のファイルにあるとき、`autopilot.py check` は、その証拠を理由に落とさない。
- R2: 証拠の `・`・`、`・`,` の後ろが `::<名前>`（同じファイルの続き）か、repo にあるファイルの path に `::` が続く形のとき、`autopilot.py check` は今までどおりそこで区切って、並べたテストをそれぞれ探し、1 つでも無ければ落とす。区切りの後ろが repo に無いファイルの path に `::` が続く形のときも落とす。
- R3: `plugin.json` の version を 0.1.3 より上げる。

## 非目標
- 評価役の定義（agents/autopilot-reviewer*.md）と qa.md の雛形の、証拠の書き方の文を変えること
- テスト名の中の `cmd:`・`manual:`・`。`・末尾の（…）を名前として読むこと（今の文法のまま、自由文・文・注記として読む）
- 区切りの後ろに repo に無い path を書いたときの、落ちる理由の文言を今のまま保つこと

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:104-110（EVIDENCE_SEP）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:770-813（evidence_problem）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:715
- 手本: plugins/spec-autopilot/tests/test_qa_evidence.py:16-27（check_with。一時の repo の qa.md の証拠を書き換えて CLI の check を回す）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_autopilot.py -q

## 変えない挙動
- 評価役が書く形（pytest の node id、`・`・`、`・`,` での並べ方、`::` の続き、cmd・注記）を受ける: plugins/spec-autopilot/tests/test_qa_evidence.py::test_check_accepts_the_forms_the_reviewer_writes
- 並べたテストが 1 つでも無ければ落とす: plugins/spec-autopilot/tests/test_qa_evidence.py::test_check_fails_when_any_listed_test_is_missing
- jest の名前の中の `:`・`、` を受ける: plugins/spec-autopilot/tests/test_qa_evidence.py::test_check_keeps_accepting_a_jest_name_with_colons_and_commas

## 前提
- 目的に届く: 評価役が名前に区切りの記号を含むテストを書いたときの往復は無くなる。直しは plugin を入れ直した後に始めたセッションの check にだけ効く
- 運用: /autopilot の main が評価役の行を qa.md に写し、`autopilot.py check` を回す（今までどおり）
- 普通のやり方: なし（この plugin に固有の証拠の文法で、外に同じ種類のものが無い）
- 過去: 区切りの先読み（直後が `::` のときだけ区切る）は、jest の名前の中の `、` で区切らないために入っている（autopilot.py:108 のコメントと test_check_keeps_accepting_a_jest_name_with_colons_and_commas）。名前の後ろに `::` が続く形は考えに入っていなかった
- 前提: 区切りの記号の直後に、空白・区切り・`:`・括弧・バッククォートを含まない語と `::` が続けば区切る。名前の中の `・`・`、` の後ろに `::<名前>` が続くと、名前の後半を path と読んで落ちる
  - path: plugins/spec-autopilot/scripts/autopilot.py:108（EVIDENCE_SEP）
  - path: plugins/spec-autopilot/scripts/autopilot.py:786-790（区切った後、`::` の前を path と読む）
  - コマンド: `一時の repo（tests/test_autopilot.py の approved と make_done）に core.test.js を「describe('得点・レベル', … test('1 行消すと、100 点', …」で置き、qa.md の R1 の証拠を core.test.js::得点・レベル::1 行消すと、100 点 にして autopilot.py check` → exit 1、「ERROR: R1 の証拠: レベル が無い」
  - コマンド: `evidence_problem に core.test.js::得点、レベル::A を渡す` → 「レベル が無い」。core.test.js::1 行消すと、100 点 と core.test.js::落下・固定（名前の後ろに :: が無い）は通る
- 前提: 証拠の path は repo の root から読み、ファイルでなければ「<path> が無い」で落とす
  - path: plugins/spec-autopilot/scripts/autopilot.py:793-801
- 前提: autopilot.py は 1498 行で、1 ファイル 1500 行の目安の近くにある
  - コマンド: `wc -l plugins/spec-autopilot/scripts/autopilot.py` → 1498

## 作り方
この spec の ADR のとおり、`EVIDENCE_SEP` の先読みで区切りの候補を見つけた後、候補の後ろの `::` の前（path の部分。前後の空白とバッククォートを除く）が空か、repo の root から見てファイルであるときだけ区切る。どちらでもなければ、記号ごと前のテストに戻して 1 つの名前として探す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、`describe` の名前に `・`・`、`・`,` を含む jest のテストを置き、その `<path>::<describe>::<test>` を qa.md の証拠にして CLI の check を回す（`・` で別のファイルのテストを並べた形も） | base で「<名前の後半> が無い」で落ち、tip で終了コード 0 |
| R2 | 手元で実物 | 既存の test_qa_evidence.py を回し、区切りの後ろに repo に無い path を書いた証拠と、名前に区切りの記号を含むテストの後ろに無いテストを並べた証拠で CLI の check を回す | 既存のテストが通り、足した 2 つはどちらも終了コード 1 |
| R3 | 手元で実物 | plugin.json と marketplace.json を読み、test_spec_autopilot_wiring.py を回す | version が 0.1.3 より上で、テストが通る |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: bug-fix
- autopilot.py は 1500 行を超えない（超えるなら、挙動を変えない別の commit で行を減らすか、証拠を読む関数を別のモジュールに移す）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
