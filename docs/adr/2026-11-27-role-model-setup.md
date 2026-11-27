# ADR: 役ごとのモデルの既定を手元の設定で上書きし、init で spec の `## モデル` に写す

## 状況
実装役・評価役のモデルと effort は、agent の定義（`agents/*.md` の frontmatter）で固定している。始めの段を変える道は、spec ごとに `## モデル` 節へ書くことだけで、利用者が手元で既定を変える設定と setup の command は無い。人は pstack の `/setup-pstack`（役ごとのモデルを対話で選び、`~/.claude/rules/pstack-models.md` に書き出し、各 skill がそれを読んで subagent にモデルを渡す）のような機能を求めた。

spec-autopilot は Agent の起動に model を渡さない（`sonnet` の別名は Sonnet 5.5 でなく Sonnet 5 に解決され、effort は起動で渡すと main の判断に寄る）。段ごとに agent の定義を分け、handoff が「dispatch が出した名前の agent が定義の model・effort で動いたか」を見ている（`scripts/ladder.py` の先頭）。

## 決定
- 手元の設定は `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `models.md` に、spec の `## モデル` 節と同じ形（`- 実装: <段>`・`- 評価: <段>`）で置く。受ける段は `ladder.RUNGS` の段だけ
- `ladder.py setup`・`ladder.py show`・`ladder.py setup --reset` で書く・見る・消す。対話は command（`/spec-autopilot:setup`）が AskUserQuestion で行い、選んだ段でこの CLI を打つ
- `autopilot.py init` が spec.md を作るとき、設定の行を `## モデル` 節に写す。梯子（`climb`）は今までどおり spec の節だけを読む

## 理由
- 写す形なら、承認のときに人が spec の上で段を見て直せ、run の途中で手元の設定を変えても走っている spec の段は変わらない（再現できる）。梯子・dispatch・handoff・lint のコードを変えずに済む
- 同じ形の行なら、設定の検査に `ladder.lint` をそのまま使える

## 退けた案
- 梯子が実行のたびに手元の設定を読む: spec に段が見えず、承認の後に設定を変えると、走っている spec の段が変わる。climb の呼び出し元（autopilot.py・overnight.py）すべてに読み手が要る
- pstack と同じく、規則ファイルに任意のモデル名を書いて起動のときに model を渡す: 「model を渡さない」と handoff の照合を崩す。Agent の model は別名しか受けず、effort を起動ごとに固定できない
- setup が agent の定義（`agents/*.md`）を書き換える: plugin の更新で上書きされ、段ごとに定義を分けた梯子と handoff の照合が合わなくなる
- 照合役・相談役のモデルも設定できるようにする: 相談役は「別のモデルで見る」ことが役で、利用者が同じモデルにすると役が消える。今回は求められた実装役・評価役の 2 つに絞る
