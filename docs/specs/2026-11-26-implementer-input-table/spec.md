# 実装役は、入力の表のテストの欄だけを埋め、今の結果を変えない

- ADR: docs/adr/2026-11-26-implementer-input-table.md

## 目的
評価役が high を返すと、`inputs/R<n>.md`（落ちた入力の種類の表）ができ、実装役がテストの欄を `<path>::<テスト名>` で埋める。今の結果の欄は評価役が確かめて書くもので、実装役は変えない。体験会のリハーサルでは、実装役が今の結果を「直した後の pass」に書き換え、handoff が「fail の行が 1 つも無い」で拒んだ。main が「落ちた入力の行を fail に戻す」commit を 2 回打って往復した。実装役の定義には入力の表の扱いが書かれておらず、実装役が読むのは定義と spec のディレクトリだけなので、定義に規則を足して、体験会で同じ往復を出さないようにする。

## 要件
- R1: 実装役の 4 つの定義（autopilot-implementer・-opus・-opus-xhigh・-fable）の手順は、`inputs/R<n>.md` があるとき、テストの欄だけを `<path>::<テスト名>` で埋め、入力の種類・例・期待・今の結果の欄と、表の行の数を変えないことを、同じ文で示す。4 つの定義の本文は今と同じく一致する。

## 非目標
- handoff が、dispatch の時点の表と比べて今の結果の書き換えを拒むこと（定義の直しで足りなければ、次に測ってから足す）
- 評価役の定義を変えること
- 入力の表のテストの欄の ERROR の文言を変えること（別の PR で直した）

## 影響範囲
- 変える: plugins/spec-autopilot/agents/autopilot-implementer.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-fable.md（全体）
  - メモ: 4 つとも、変えるのは手順 7 の次の 1 項の追加と、後ろの番号の送りだけ
- 呼び出し元: なし
- 手本: plugins/spec-autopilot/agents/autopilot-implementer.md:20（手順 7、評価役の .autopilot-qa を変えない規則）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py -q

## 変えない挙動
- 梯子の各段の実装役は、宣言の model・effort を持ち、本文が一致する: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body
- 既定の実装役は sonnet-high で、段はそこから上がる: plugins/spec-autopilot/tests/test_ladder.py::test_the_default_implementer_is_sonnet_high_and_the_rungs_rise_from_it

## 前提
- 目的に届く: 実装役が定義の規則に従うかは、文を足しただけでは確かめられない。次の run で inputs の今の結果が実装役の commit で変わったかを見て測る
- 運用: 利用者は何もしない。実装役が定義を読んで従う
- 普通のやり方: なし（この plugin 固有の agent 定義で、比べる普通のやり方が無い）
- 過去: 実装役の定義に入力の表の扱いを足した PR は無い（git log -- plugins/spec-autopilot/agents/autopilot-implementer.md で確かめた）
- 前提: 実装役の定義は、入力の表（inputs・今の結果）に触れていない
  - コマンド: `grep -n "inputs\|今の結果" plugins/spec-autopilot/agents/autopilot-implementer.md` → 0 件
- 前提: 今の結果は評価役が書き、handoff は fail の行が無い表を拒む
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:59（今の結果は評価役が確かめた結果を書く）、plugins/spec-autopilot/scripts/overnight.py:554-555（fail の行が 1 つも無い表を拒む）
- 前提: リハーサルで、実装役が今の結果を pass に書き換え、main が fail に戻す commit を 2 回打った
  - 未確認: リハーサルの repo は手元の一時ディレクトリにあり、この repo の path では示せない（commit の件名は「T5: R11・R12 の入力表のテスト欄を埋め、今の結果を直した後の pass に書き換え」と「spec: 入力の表の落ちた入力の行を fail に戻す」）
- 前提: 実装役の 4 つの定義は本文が一致し、テストが突き合わせる
  - path: plugins/spec-autopilot/tests/test_ladder.py:199-211

## 作り方
4 つの定義の手順 7（.autopilot-qa を変えない）の次に、入力の表の規則を 1 項足し、後ろの手順の番号を 1 つずつ送る。4 つとも同じ文にする。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 回帰テストを回し、4 つの定義の本文（frontmatter の後）を diff で突き合わせ、足した項を読む | 回帰テストが通り、4 つの本文が一致し、足した項がテストの欄だけを埋めて今の結果などほかの欄と行の数を変えないことを示す |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: なし（agent 定義の文の直しで、当たる種類が無い）

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
