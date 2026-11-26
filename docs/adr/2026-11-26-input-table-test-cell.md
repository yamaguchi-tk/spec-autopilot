# ADR: 入力の表のテストの欄の ERROR は、入力の表で使える形だけを示す

- 日付: 2026-11-26
- 状態: Accepted
- spec: docs/specs/2026-11-26-input-table-test-cell

## Context
`overnight.py handoff` は、`inputs/R<n>.md` のテストの欄が空・`-`・`cmd:`・`manual:` を含む・`::` の無い形だと拒む。そのときの ERROR は qa.md の証拠の形の文（EVIDENCE_FORMS）を借りていて、拒んだ `cmd:`・`manual:` を使える形として挙げる。

## 選択肢
1. **入力の表で、形が読めないときだけ入力の表専用の文にする**
   - 得るもの: 直す箇所が 1 か所で、`<path>::<テスト名>` の形の行の文（無いテストの名前など）は今のまま残る
   - 失うもの: 形の説明の文が 2 つになる
2. **EVIDENCE_FORMS の文を変える**
   - 失うもの: qa.md の証拠では cmd:・manual: が使えるので、qa.md の検査の文が誤りになる

## Decision
1 を選ぶ。

## Consequences
- 実装役は、handoff の ERROR から入力の表に書ける形を読める
- qa.md の検査の文言は変わらない
