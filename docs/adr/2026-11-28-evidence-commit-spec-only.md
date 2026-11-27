# ADR: 手元で実物の証拠の commit を、spec の置き場の外が同じなら巡の tip と同じとみなす

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-evidence-commit-spec-only

## Context
check は、手元で実物の証拠の頭の `- commit:` を、評価役の巡の sha と文字列で比べる。評価役が返った後に main が state や qa.md を commit すると、評価役が書いた commit と巡の記録の sha がずれ、コードが同じでも check が止まった。

## 選択肢
1. 文字列で一致しないとき、2 つの commit の間で spec の置き場の外が同じかを git で見る: carry.py の same_outside と同じ照合で、コードが同じことだけを確かめる
2. review の記録に、評価役が見た tip と main が記録した時点の HEAD の両方を残す: 記録の形が変わり、読む側が増える
3. main の手順で、評価役の後の commit を check の後に回す: 手順の順に頼り、崩れたときに同じ詰まりに戻る

## Decision
1 を選ぶ。比べられないとき（commit が無い・git が失敗する）は同じでないとし、今までどおり落とす。時刻の条件は変えない。証拠の頭の値は評価役（LLM）が書くので、git の option として読まれないよう `git rev-parse --verify --end-of-options <値>^{commit}` で sha に引き当ててから比べる。値の形（16 進だけ）で先に落とす案は、親の R3 が数える証拠（sha でない commit の名前）を落とすので採らない。

## Consequences
- spec の置き場の中だけの commit が評価役の後に挟まっても、評価役を回し直さずに check が通る
- 評価役の後にコードを変えたときは、今までどおり評価役を回し直す
