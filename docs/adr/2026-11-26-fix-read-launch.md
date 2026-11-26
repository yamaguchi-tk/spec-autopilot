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
