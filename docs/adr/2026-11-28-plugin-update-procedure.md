# ADR: 手元の plugin の更新の規則を marketplace の更新に置き換え、pull の手順を消す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-plugin-update-procedure

## Context
手元の plugin は、symlink で手元の checkout を直接読んでいた。checkout を動かすと全セッションの hook がその場で変わるので、CLAUDE.md の規則と docs/pull-checkout.md で、pull を人が頼んだときだけ差分の判定つきで行うことにしていた。2026-11-28 に、人の決定（「A に移す」）で、GitHub の marketplace から版ごとの写しを入れる形に移した。規則と手順の対象（symlink の向け先の checkout）が無くなった。

## 選択肢
1. CLAUDE.md の行を marketplace の更新の規則に置き換え、docs/pull-checkout.md を消す: 正本が実際の入れ方と一致する。手順の細部（plist の出し直しなど）は CLAUDE.md の 1 行に入れる
2. docs/pull-checkout.md の中身を更新の手順に書き換えて名前を残す: ファイルの名前と中身がずれる
3. 何も変えない: 対象の無い手順が正本として残り、agent が checkout の pull を試みる

## Decision
1 を選ぶ。更新の手順は 3 つの操作（update・/reload-plugins・plist の出し直し）だけで、別のファイルに分けるほど長くない。

- 直し方: 要らなくする
- 退けた: なし（最上段の「要らなくする」を選んだ。pull の手順そのものを消す）

## Consequences
- 手元に直しを届けるには、版数を上げて人が update する。版数を上げない直しは手元に届かない
- 版の更新のたびに見回り役の plist が古い版を指すので、人が出し直す。preflight での検知は別の spec にする
