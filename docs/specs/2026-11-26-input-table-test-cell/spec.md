# 入力の表のテストの欄が使えないとき、入力の表で使える形だけを示す

- ADR: docs/adr/2026-11-26-input-table-test-cell.md

## 目的
評価役が high を返した後、実装役は `inputs/R<n>.md`（落ちた入力の種類の表）のテストの欄（評価役は `-` で出す）を `<path>::<テスト名>` で埋める。埋め忘れた `-` や、`cmd:`・`manual:` を書くと `overnight.py handoff` が拒むが、その ERROR は qa.md の証拠の形（「続けて ` と cmd: ...` か、`cmd: ...`・`manual: ...`」）を示し、拒んだ当の `cmd:` を使える形として挙げる。読んだ実装役は直し方を取り違えうる。入力の表で使える形（`<path>::<テスト名>` だけ）を示し、体験会で初めての人の run が同じ往復で止まらないようにする。

## 要件
- R1: 入力の表のテストの欄が、空・`-`・`cmd:` か `manual:` を含む・`<path>::<テスト名>` の形でない、のどれかの行があるとき、`overnight.py handoff` は今と同じく失敗し、ERROR は、その欄には `<path>::<テスト名>`（複数は `・` で並べる）だけを書けることと、`cmd:`・`manual:` は書けないことを示し、`cmd: ...`・`manual: ...` を使える形として示さない。

## 非目標
- qa.md の証拠の形（EVIDENCE_FORMS）と、qa.md を読む check の文言を変えること
- テストの欄が `<path>::<テスト名>` の形で、テストが repo に無いとき・中身が空の `cmd:` のときの文言を変えること
- 評価役・実装役の agent 定義を変えること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:569-579（input_handoff_errors）
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1035
- 変える: plugins/spec-autopilot/tests/test_input_kinds.py:166-170（test_handoff_refuses_a_free_text_test_cell）
- 手本: plugins/spec-autopilot/scripts/overnight.py:582-593（input_fail_errors）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_input_kinds.py -q

## 変えない挙動
- テストの欄が `-` の行は handoff が拒む: plugins/spec-autopilot/tests/test_input_kinds.py::test_handoff_refuses_a_row_whose_test_cell_is_a_dash
- repo に無いテストは handoff が拒む: plugins/spec-autopilot/tests/test_input_kinds.py::test_handoff_refuses_a_test_that_is_not_in_the_repo
- どの行も repo のテストを指せば handoff が閉じる: plugins/spec-autopilot/tests/test_input_kinds.py::test_handoff_closes_when_every_row_names_a_test_in_the_repo

## 前提
- 目的に届く: 文言だけの直しで、拒む条件は変えない。実装役が ERROR を読んで直すことは、ERROR の文が正しい形を示すことに頼る
- 運用: 利用者は何もしない。実装役が handoff の ERROR を読んで表を直す
- 普通のやり方: なし（この plugin 固有の検査の文言で、比べる普通のやり方が無い）
- 過去: input_handoff_errors の文言を扱った PR は無い（git log -- plugins/spec-autopilot/scripts/overnight.py で確かめた）
- 前提: テストの欄が空か cmd:・manual: を含むとき、input_handoff_errors は qa.md の証拠の形の文 EVIDENCE_FORMS をそのまま ERROR に入れる
  - path: plugins/spec-autopilot/scripts/overnight.py:576（EVIDENCE_FORMS を bad に入れる）、plugins/spec-autopilot/scripts/autopilot.py:110（EVIDENCE_FORMS が cmd: と manual: を使える形として挙げる）
  - コマンド: `python3 -m pytest <テストの欄に cmd: 手で見た を書いた表で handoff を回す一時テスト> -s` → ERROR: inputs/R1.md のテストの欄が使えない（形が読めない（`<path>::<テスト名>` を `・` で並べ、続けて ` と cmd: ...` か、`cmd: ...`・`manual: ...`））
- 前提: テストの欄が `-` か、`::` の無い形の崩れた行でも、evidence_problem は同じ EVIDENCE_FORMS を返す。評価役は表のテストの欄を `-` で出すので、埋め忘れの `-` が最も出やすい
  - path: plugins/spec-autopilot/scripts/autopilot.py:778-791（evidence_problem が EVIDENCE_FORMS を返す 3 か所）、plugins/spec-autopilot/agents/autopilot-reviewer.md:59（テストの欄は `-` にする）

## 作り方
input_handoff_errors で、テストの欄が空か自由文（EVIDENCE_FREE に当たる）のときと、evidence_problem が EVIDENCE_FORMS を返したときに、EVIDENCE_FORMS の代わりに入力の表専用の文（`<path>::<テスト名>` を `・` で並べた形だけを書ける。`cmd:`・`manual:` は書けない）を入れる。evidence_problem のほかの文（無いテストの名前など）は今のとおり使う。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | テストの欄に `cmd: 手で見た`・`manual: 見た`・`<path>::<テスト名>。加えて cmd: x`・`-`・`test_rule.py`（`::` なし）を書いた入力の表で、本物の `overnight.py handoff` を回す | 終了コードが 0 でなく、ERROR に `<path>::<テスト名>` と「書けない」があり、` と cmd: ...` と `manual: ...` を使える形として示す文が無い。base で落ち、tip で通る |

## 制約
- 予算: 30 分
- 大きさ: S
- playbook: bug-fix

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境: 手元
- QA の書き込み先: なし
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: なし
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
