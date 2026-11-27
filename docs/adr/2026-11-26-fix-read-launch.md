# ADR: subagent の transcript を "\n" だけで割る直しを、リファクタと別の spec にする

- 日付: 2026-11-26
- 状態: Accepted
- spec: docs/specs/2026-11-26-fix-read-launch

## Context
2026-11-26-split-transcript の handoff が、実装役の transcript の U+2028 で止まった。read_launch と advisor_approval.launches が str.splitlines で割るため。CLI は手元の checkout から動くので、worktree で直しても人が pull するまで効かない。

## 選択肢
1. 別の bug-fix の spec で直し、マージ後に人が pull して split-transcript を resume する: 1 PR 1 課題を守り、照合の門を残す。pull の分だけ人の手が要る
2. split-transcript に直しを混ぜる: 挙動を変えないリファクタに挙動の直しが混ざる。pull までは結局通らない
3. worktree の直した overnight.py で 1 回だけ handoff を打つ: 自分を止める門を自分で直した版で通す
4. 照合を外す: 事故を防ぐ門を外す

## Decision
1 を選ぶ（相談役の推奨。検証役の判定は反証なし）。同じ割り方の advisor_approval.launches も同じ入力なので一緒に直す。

## Consequences
- split-transcript は pull まで blocked のまま
- 割り方の正本が transcript_lines と別に 2 か所残る（split-transcript の後に別の spec でまとめる）
- awaits.jsonl に切れた行が 1 行でも残ると、人がその行を直すか消すまで、その spec の待ちの記録を読む判定は全部止まる。Stop hook の文は例外の型名だけなので、行番号は CLI を回して見る
- 書き手が書いている途中に読むと、書きかけの末尾の行で一時的に止まりうる（次の判定で消える。頻度は測っていない）

## pre-pr-review の範囲
- 範囲: overnight.read_launch と advisor_approval.launches が subagent の transcript を、overnight._awaits が awaits.jsonl を、"\n" だけで割るようにする（JSON の文字列の中の U+2028・U+2029・U+0085 で行を割らない）。壊れた行は、transcript では今までどおり読めない記録として止め、awaits.jsonl でも飛ばさずにファイルと行番号を名指しして止める。await の書き手は、前の記録が改行で終わらなければ改行を足してから書く
  - _awaits は 1 巡目の独立レビューの high（deploy の failure の行が割れて飛ばされ、failed_deploys・deploy_smoke が数え漏れて ready と check が通す側に倒れる fail-open）で、人に確かめて範囲に入れた
  - 2 巡目の独立レビューの high（切れた行を飛ばし、書き手が改行を確かめないので次の記録も同じ行になって飛ぶ）で、同じ部品に 2 巡続けて high が出たので再設計にした。案は「源で止める」と「書き手だけ直して飛ばす挙動を保つ」で、人が「源で止める」を選んだ
- 想定する脅威: 事故だけ（subagent が読んだファイルの中身に、改行に似た文字が入っていること）。transcript をわざと書き換える入力は想定しない
- やらないこと: 割り方の関数を 1 つにまとめること、相談役の返答の本文の割り方（_lines_of）、ほかの splitlines の箇所（JSONL を読まないもの）、Stop hook が止めたときの文に行番号を出すこと（hooks/stop.py は変えない）、版数
