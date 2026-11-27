# 承認の前の試作（大きさ S の spec と、新しく作る repo の M の spec）

次のどちらかの spec では、承認の前に動く試作を作って人に触ってもらう（`commands/autopilot.md` の A の 2 から読む。playbook の名前ではなく、大きさの行と repo の種類で決まる）。

- `- 大きさ: S`
- `- 大きさ: M` で、新しく作る repo（state.json の `existing` が false〔bool〕。キーが無い・ほかの値なら既存の repo とみなす。false は、init のときに docs/specs・docs/adr の外に git が追うファイル（git の外では、ファイル）が無ければ init が書く。dispatch と hook は state.json の `existing` だけを見る）で、「## 制約」に `- 依る spec:` の行が無い。依る spec のある M は、前の spec の変更がまだ載っていない木に書くことになるので作らない。既存の repo の M・L も承認の前にコードを書かない

M の試作も実装役 1 本に全要件を渡す（新しく作る repo の M の実装と同じ）。草案の提示は S より遅れうるので、予算の 10 分に触れるまでを数えて報告に書く。

## いつ・誰が作るか

- 草案の要件どおりに動く版を、草案の `## モデル` の `- 実装:` の段の agent（無ければ `autopilot-implementer`。名前は `scripts/ladder.py` の RUNGS）に書かせる。渡すのは spec のディレクトリと「全要件」だけ。単体テスト込み、作業ブランチに commit。tasks.md の先頭に playbook のタスクがあれば、その順に 1 タスク 1 commit で書かせる（bug-fix なら、落ちる再現のテストを直しと別の commit にする）
- 起動の前に: tasks.md に全要件を受け持つタスクを書き（playbook のタスクがあれば先頭に）、`overnight.py dispatch <dir> --task T<n>...` を打つ（discovery では上の 2 種類だけ受ける。最後の行が起動する agent の名前。打たずに起動すると hook が deny する）
- 起動の時機: spec.md の要件を書いて `CLI lint` を通し、B の 3 の照合役が返って `ng` を直した後。ADR を書く Write と同じメッセージに並べる（どちらも前景で、並行に走る。implementer は ADR を読まない。照合役は作業ツリーを読むので、試作が書き換えている間には回さない）
- 依存は入れない（承認の前なので）

## 示し方

- 草案と一緒に「触ってみてください: <開き方>」と添える
- 人は文より動くものを見て、本当に欲しいものに気づく（計測では、spec の文だけを見せた壁打ちは「壁で死なずに反対側から出る」「表示は日本語」などの要望を引き出せず、利用者が本当に欲しかったものの充足は、動くものを先に見せて直した素の Claude Code の 26/30 に対し 19/30 だった。試作を先に見せる形にすると 26/30 で並んだ）
- 直しが返ったら、spec を直し、直した要件を implementer に渡して試作も直させてから示し直す
- 試作を作ったら `CLI lint` を回し直してから示す（差分が無い S は、lint は NOTE、`CLI approve` は ERROR にする）

## 承認の後

- C の 1 で tasks.md を書き、試作で済んだタスクを `[x]` にして `overnight.py handoff <dir> --task T<n>...` で試作の dispatch を閉じる（承認は dispatch を消さない）。残りを実装してから C の 3 の評価に進む
