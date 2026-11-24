# ADR: 大きさ S の試作の dispatch と実装役の起動を、承認の前（discovery）でも受ける

## 状況
`references/small-prototype.md` は、大きさ S の spec で承認の前に実装役に試作を書かせると定めている。一方で `overnight.py dispatch` は phase が building のときだけ受け、実装役の起動の入口の hook（`hooks/agent_gate.py`）も building でない spec の起動を deny する。そのため手順どおりに進めると、試作を作れない（2026-11-24 の試走で、dispatch が exit 1、hook が deny した）。

## 決定
dispatch と hook が受ける phase を「building、または discovery で `## 制約` の大きさが S」に広げる。discovery の S の spec では、承認の前の実装役の起動はすべて試作なので、試作かどうかの印を別に持たない。handoff は今までどおり building だけ受け、試作の dispatch は承認の後に handoff で閉じる。そのため承認（`lineup.begin`）は、discovery からの承認では dispatches・handoffs を消さずに持ち越す（discovery でこれらを作るのは S の試作だけ）。

## 退けた案
- dispatch に `--prototype` のような印を足し、hook がその印を見る: discovery の S では起動はすべて試作なので、印は見分けを増やさず、打ち忘れの道を 1 つ増やす
- 承認の後に dispatch を打ち直す: base が試作の後になり、handoff が「commit が無い」で拒む。試作の起動の確かめも消える
- 試作だけ main が書く: 「main は書かない」と、handoff の起動の確かめ（定義の model・effort で動いたか）から外れる
- handoff も discovery で受ける: 試作の後に評価役は回らないので、閉じる必要が無い。承認の後の C の 3 の前の handoff で閉じれば足りる

## 結果
- discovery で大きさが S でない spec の dispatch と起動は、今までどおり止まる
- spec.md の大きさの行を S に書き換えれば承認の前に実装役を起動できる。承認の lint が数えた大きさで S を確かめるので、ここでは事故（打ち忘れ・M 以上での承認前の実装）だけを止める
