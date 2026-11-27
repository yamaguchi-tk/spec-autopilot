# handoff が「遊べます」の行を促し、触れるまでの時間をマージの前に測る

- ADR: docs/adr/2026-11-27-handoff-playable-line.md

## 目的
人の言葉:「10分で終わらないのは時間かかりすぎ」。どの時点を 10 分にしたいかを聞くと「触れるまで」。そのうえで「A+Bで進めて」「テストを絞ってもいい」。

観測した失敗は、0.1.16 でのハンズオンの試走（2026-11-27、Sonnet 5.5、新しい repo、ブラウザのテトリス）である。触れる状態になったのは送信の約 13 分後だが、main は commands/autopilot.md の「遊べます: <開き方>。評価を続けます」の行を出さずに評価役へ進み、人が触れてよいと分かったのは done の 23 分 48 秒後だった。この行は文書の指示だけで、scripts と hooks には無い。前の 2 本の直し（s-prototype-size・s-prototype-tests）は実測をマージの後に回し、試走で経路に乗らないと分かったのはマージの後だった。

できあがったら、最後のタスクを閉じた handoff が「遊べます」の行を出すよう促し、触れるまでの時間をマージの前に同じ依頼文で測ってから入れる。

2 本に分けた spec の 2 本目である。1 本目（new-repo-m-one-implementer）は、新しく作る repo の M でも実装役 1 本・代表のテストで書かせる。

## 要件
- R1: overnight.py handoff が実装役の dispatch を閉じて OK を返し、そのとき tasks.md のタスクの行が全部 `[x]` なら、handoff は OK の行に続けて、触れるものなら評価役に進む前に「遊べます: <開き方>。評価を続けます」の 1 行を出すよう促す行を出す。`[ ]` のタスクが残るときは、その行を出さない。handoff の判定（通す・止める）と state.json の記録は変えない。
- R2: 1 本目と 2 本目の変更が載った plugin で、新しく作る repo にブラウザのテトリスを頼んだとき、依頼の送信から「遊べます」の行が出るまでの時間は、人の OK にかかった時間を 3 分に置き換えて 10 分以内になる。

## 非目標
- 大きさ M でも承認の前に試作を作ること（R2 が 10 分を超えたら、数字を添えて人に戻す）
- 「遊べます」の行が出たかを機械で検査すること（出すのは main の text で、handoff は促すだけ）
- 版数を上げること（マージの後に、repo の CLAUDE.md の 1 段目で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:1048-1090（cmd_handoff）
- 変える: plugins/spec-autopilot/tests/test_overnight.py:607-620（test_handoff_requires_a_new_commit_and_checked_tasks）
  - メモ: この近くに、全部 [x] のときだけ促す行が出るテストを足す
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:93
  - メモ: C の 3 の handoff の項が overnight.py handoff を打つ
- 手本: plugins/spec-autopilot/scripts/overnight.py:1068-1069（記録済みのときの print の書き方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_input_kinds.py plugins/spec-autopilot/tests/test_prototype_gate.py -q -n auto

## 変えない挙動
- handoff は新しい commit と [x] を求める: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_requires_a_new_commit_and_checked_tasks
- handoff は commit していないコードを拒む: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_rejects_uncommitted_code

## 前提
- 目的に届く: 行を出すのは main で、handoff は促すだけなので、main が促しを無視すれば出ない。10 分に届くかは R2 の 1 回の試走で測るだけで、ぶれは測らない
- 運用: /autopilot の main が C の 3 で handoff を打ち、出力を読む。R2 の試走は、人が tmux の中の入れ子の Claude Code で権限の確認と草案の OK を返す
- 普通のやり方: なし（agent に出させる行を CLI の出力で促す、決まった作り方は無い）
- 過去: docs/specs/2026-11-27-s-prototype-tests（実測をマージの後に回し、経路に乗らないと分かったのはマージの後だった）
- 前提: 「遊べます」の行は autopilot.md の文だけで、scripts と hooks には無い
  - コマンド: `grep -rn 遊べます plugins/spec-autopilot` → commands/autopilot.md:91 の 1 件だけ
- 前提: handoff は OK のとき「handoff: OK。評価役に進む」を出し、tasks.md の [x] のタスクを読む
  - path: plugins/spec-autopilot/scripts/overnight.py:1083-1090
- 前提: R2 の試走の時点で、1 本目の変更（実装役の 2 の項と autopilot.md の新しく作る repo の M の扱い）がこの worktree の plugin に載っている
  - 未確認: 1 本目はまだ承認の前で commit が無い。着手のとき lineup.py next が 1 本目の先端の上に載せ替えるので、R2 の前に plugins/spec-autopilot/agents/autopilot-implementer.md の 2 の項を読んで確かめる
- 前提: init は新しく作る repo かを state.json の existing に記録する
  - path: plugins/spec-autopilot/scripts/autopilot.py:893-897

## 作り方
この spec の ADR のとおり、cmd_handoff が OK を返すとき、tasks.md のタスクの行が全部 [x] なら、促す行を 1 行足して出す。R2 は、1 本目と 2 本目の変更が載ったこの worktree の plugin で、前回と同じ依頼文の試走を 1 回回して測る。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、tasks.md が全部 [x] のときと [ ] が残るときに handoff を打つ単体テストを回す | 全部 [x] のときだけ「遊べます」を促す行が出て、どちらも終了コードと state.json の handoffs が今と同じ |
| R2 | 手元で実物 | 手元の一時のディレクトリに新しい空の git repo を作り、tmux の中で `claude --plugin-dir <この worktree>/plugins/spec-autopilot --model claude-sonnet-5-5` を起動し、前回の試走と同じ依頼文「/spec-autopilot:autopilot ブラウザで遊べるシンプルなテトリスのようなゲームを作りたい。基本の操作（移動・回転・落下・行の消去・スコア）だけでよい。自走の範囲は PR まで。GitHub に repo は作らない」を送り、草案に人が OK を返し、入れ子の transcript の時刻を読む | （草案の提示の時刻 − 送信の時刻）+ 3 分 +（「遊べます」の行の時刻 − OK の時刻）が 10 分以内 |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 依る spec: 2026-11-27-new-repo-m-one-implementer
- 脅威: なし（handoff の出力に 1 行足すだけで、判定と記録は変えない）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先: 手元の一時のディレクトリ（R2 の試走の新しい空の git repo。GitHub には作らない）
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
- R2 の実測が 10 分を超えたとき（数字を添えて人に戻し、承認の前の M の試作を相談する）
