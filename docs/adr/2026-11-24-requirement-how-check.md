# ADR: 要件の中の作り方は、承認の前に照合役の項目 10 で止める

- 日付: 2026-11-24
- 状態: Accepted
- spec: docs/specs/2026-11-24-requirement-how-check

## Context
docs/specs/2026-11-23-handoff-after-close の R3 では、レビューの high が 4 巡続いた。作り直しの ADR（docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md）は、「prompt を読まない」案を「R1・R2 が prompt で判定すると定めているので要件が変わる」として退けた。

ただし、目的（同 spec の目的の節）は「起動の時点か handoff で止まる」までで、prompt を読むことは求めていない。作り方が要件に入り、承認のハッシュ（autopilot.py の sha）と dead-end.md の「要件を緩める案は挙げない」に守られて、根本の案を締め出した。

## 選択肢
1. **照合役の表に項目 10 を足す**
   - 得るもの: 承認の前に、文の意味で見分けられる。既存の照合の流れ（main が読み直して採る）に乗る
   - 失うもの: LLM の読みで揺れる
2. **`CLI lint` に語の一覧（「prompt に書かれた」「正規表現で」など）を足す**
   - 得るもの: 決定的に動く
   - 失うもの: 外から見える約束（hooks.json の matcher など）と見分けられない。語の継ぎ足しが、それ自体で対処療法になる
3. **作り直しのときに、agent が要件の作り方の部分を書き換えてよいとする**
   - 失うもの: 承認の境界を、agent の自己申告で動かすことになる

## Decision
1 を選ぶ。見分けるのは意味（目的と合格基準に要るか）で、語ではない。誤りは、QA で handoff-after-close（ng が出るべき）と advise-stray-space（ng が出るべきでない）に当てて測る。

## Consequences
- 承認の前の照合で、ng が 1 種類増える。main が直すか、直せなければ人に示す
- 取りこぼした要件は、root-cause-fix-order の spec の park の出口で拾う
