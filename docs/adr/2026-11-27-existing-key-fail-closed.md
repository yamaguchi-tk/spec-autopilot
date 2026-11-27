# ADR: state.json に existing のキーが無いときは、既存の repo とみなす

- 日付: 2026-11-27
- 状態: Accepted
- spec: docs/specs/2026-11-27-existing-key-fail-closed

## Context
承認の前の試作の門（overnight.py の prototype_ok）は、state.json の existing を `not s.get("existing")` で読む。キーが無いと新しく作る repo とみなし、大きさ M の試作を承認の前に通す（fail-open）。lint の既存の repo の節（autopilot.py の lint）と done の大きさの数え方（autopilot.py の cmd_done）も、同じキーを同じ既定（無ければ新しく作る repo）で読む。今の init はキーを必ず書くので、キーが無いのは、手で作った・直した state.json か、キーを書く前の版で作った state.json だけである。PR 92 の評価役の low と、claude/leftover-lows の独立レビューの high が同じ問題を挙げ、人は「先に spec で直す」と決めた。

## 選択肢
1. **3 か所とも、existing が `False` のときだけ新しく作る repo とみなす（読み方を 1 つの関数にまとめる）**
   - 得るもの: キーが無い・値が bool でないときは、試作の門は M を拒み、lint は既存の repo の節を求め、done は大きさを数える。読み方が 1 か所になり、3 か所の食い違いが無くなる
   - 失うもの: キーの無い古い state.json の新しく作る repo の spec で、lint が影響範囲と変えない挙動を求めるようになる（state.json に `"existing": false` を足せば戻る）
2. **試作の門だけを直し、lint と done は今のままにする**
   - 失うもの: 同じキーの読み方が 2 通り残る。lint がキーの無い spec の既存の repo の検査を飛ばすのは、同じ fail-open である
3. **キーが無いときは state.json の読み込みでエラーにする**
   - 失うもの: state.json を読むすべての経路（hook・lineup・watch など）が止まりうる。キーを使わない経路まで巻き込む

## Decision
1 を選ぶ。

## Consequences
- 読み方は autopilot.py の関数 1 つにし、overnight.py はそれを呼ぶ（overnight.py の行は増やさない）
- init がキーを書くことは変えない
