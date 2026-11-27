# 新しく作る repo の M でも、承認の前に触れる試作を出す

- ADR: docs/adr/2026-11-27-new-repo-m-prototype.md

## 目的
人の言葉:「10分で終わらないのは時間かかりすぎ」。10 分にしたいのは「触れるまで」。PR 86 の試走の R2 を fail と記録したとき、人は「承認の前の M の試作を次の spec にする」と決めた。

観測した失敗は、PR 86 の試走（2026-11-27、Sonnet 5.5、新しい repo、ブラウザのテトリス）である。最初に触れたのは送信から 8:49 で、照合役が最初に S と見積もり、承認の前の試作を作ったからだった。試作は 278 行になり、草案は提示の時点で M に変わった。今の門（overnight.py dispatch と hooks/agent_gate.py）は、承認の前の試作を大きさ S だけに許すので、最初から M と見積もられた回では試作が出ず、触れるのは人の OK と実装の後の約 12〜13 分になる。内訳は照合役が約 2 分、試作が約 5 分（起動から提示まで 4:53）。

できあがったら、新しく作る repo では大きさ M でも草案と一緒に触れる試作を出し、人の OK を待つ時間を触れるまでの経路から外す。既存の repo の M は今のまま（承認の前にコードを書かない）にする。

## 要件
- R1: 承認の前（discovery）で、新しく作る repo の spec の「## 制約」の大きさの行が `- 大きさ: M` で、`- 依る spec:` の行が無いとき、overnight.py dispatch は試作の dispatch を記録して実装役の名前を出し、hooks/agent_gate.py はその実装役の起動を通す。既存の repo の M、依る spec のある M、L、大きさの行が無い・読めない spec では、今と同じく dispatch は state.json を変えずに拒み、hook は起動を拒む。大きさ S の扱いは変えない。
- R2: この spec の変更が載った plugin で、新しく作る repo にブラウザのテトリスを頼んだとき、試作の dispatch の時点で spec の大きさの行が M であり、依頼の送信から、試作を開き方つきで示す main の文までが 10 分以内になる。

## 非目標
- 既存の repo の M・L で承認の前に試作を作ること
- 照合役（承認の前の点検）を試作と並行に回して短くすること（照合役は作業ツリーを読むので、試作が書き換えている間には回さない。R2 が 10 分を超えたら、数字を添えて人に戻す）
- 版数を上げること（マージの後に、repo の CLAUDE.md の 1 段目で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:877-892（is_small、cmd_dispatch）
  - メモ: 5 行の使い方の docstring の「大きさ S」も書き換える
- 変える: plugins/spec-autopilot/hooks/agent_gate.py:89-91（problem）
  - メモ: 1-3 行の docstring の「大きさが S の試作」も書き換える
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: A の 0・2・3 の試作の項（42-58 行）と、承認の前にコードを書かない例外（81 行）
- 変える: plugins/spec-autopilot/references/small-prototype.md（全体）
- 変える: plugins/spec-autopilot/README.md（全体）
- 変える: plugins/spec-autopilot/tests/test_prototype_gate.py:49-71（test_dispatch_in_discovery_refuses_a_spec_that_is_not_small_and_keeps_state、test_gate_denies_in_discovery_when_the_size_is_not_small_even_with_a_dispatch_record）
  - メモ: test の repo の fixture は新しく作る repo なので、M を拒むテストは既存の repo に直し、新しく作る repo の M を通すテストを足す
- 呼び出し元: plugins/spec-autopilot/hooks/agent_gate.py:89
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:890
- 手本: plugins/spec-autopilot/scripts/lineup.py:30-31（after_name。依る spec の行の読み方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_advisor_approval.py -q -n auto

## 変えない挙動
- 大きさ S の試作の dispatch は通る: plugins/spec-autopilot/tests/test_prototype_gate.py::test_dispatch_in_discovery_accepts_a_small_spec_and_prints_the_implementer
- dispatch の無い試作の起動は拒む: plugins/spec-autopilot/tests/test_prototype_gate.py::test_gate_denies_in_discovery_for_a_small_spec_without_a_dispatch
- 承認の後の handoff が試作の dispatch を閉じる: plugins/spec-autopilot/tests/test_prototype_gate.py::test_handoff_closes_the_prototype_dispatch_after_approval
- spec.md が読めないことを dispatch と hook が言う: plugins/spec-autopilot/tests/test_prototype_gate.py::test_dispatch_and_gate_say_that_spec_md_could_not_be_read

## 前提
- 目的に届く: 門を開けても、main が M で試作を作るのは autopilot.md の文に従うときだけで、機械では強いない。10 分に届くかは R2 の 1 回の試走で測るだけで、ぶれは測らない
- 運用: /autopilot の main が A の 2 で、S か新しく作る repo の M なら試作を dispatch する。R2 の試走は、人の代わりにこのセッションが tmux の中の入れ子の Claude Code に依頼文を送り、時刻を読む
- 普通のやり方: なし（承認の前に試作を出す範囲を repo の種類で決める、決まった作り方は無い）
- 過去: docs/specs/2026-11-27-handoff-playable-line（R2 の試走が 12:51 で 10 分を超え、最初に触れたのは S の試作の 8:49 だった）
- 前提: 承認の前の dispatch は大きさ S だけを受け、hook も同じ関数で決める
  - path: plugins/spec-autopilot/scripts/overnight.py:877-892（is_small と cmd_dispatch）
  - path: plugins/spec-autopilot/hooks/agent_gate.py:89-91
- 前提: init は新しく作る repo かを state.json の existing に記録し、existing は git が追う docs/specs・docs/adr の外のファイルがあるかだけで決まる（追っていないコードだけがある repo は新しく作る repo になる）
  - path: plugins/spec-autopilot/scripts/autopilot.py:867-897（has_code と cmd_init）
  - メモ: 追っていないコードだけの repo で M の試作が通るのは受け入れる。S の試作は今もその repo で通り、試作は commit するので消えない
- 前提: 同じ依頼文でも草案が S になりうる。M になるかは main が大きさの表と playbook の S の行数の規則で決める
  - path: plugins/spec-autopilot/commands/autopilot.md:48-54（大きさの表）
  - path: plugins/spec-autopilot/references/playbooks/feature.md:12（S の草案は本体 200 行に収める）
- 前提: 承認は試作の dispatch を大きさによらず持ち越し、承認の後の handoff で閉じる
  - path: plugins/spec-autopilot/scripts/lineup.py:82-85（begin）
- 前提: 新しく作る repo の M は、実装役 1 本・代表のテストで書く
  - path: docs/adr/2026-11-27-new-repo-m-one-implementer.md
- 前提: overnight.py は 1508 行で、コード健全性の目安の 1500 行を超えている
  - コマンド: `wc -l plugins/spec-autopilot/scripts/overnight.py` → 1508
  - メモ: overnight.py の行は増やさない

## 作り方
この spec の ADR のとおり、新しく作る repo かは state.json の existing で読み、試作を許す判定を、大きさ S か、新しく作る repo で依る spec の無い M にする。判定は overnight.py の is_small の位置で 1 つの関数にまとめ、dispatch と hook が同じものを使う（overnight.py の行は増やさない）。commands/autopilot.md の A の 2・3 と references/small-prototype.md は、新しく作る repo の M でも試作を作ると書く。試作の行数で大きさを決め直す話は S のまま残す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、新しく作る repo の S・M・依る spec のある M・L・大きさの行が無い spec と、既存の repo の M の spec を discovery に置き、overnight.py dispatch と hooks/agent_gate.py を入口から打つ | 新しく作る repo の S と M（依る spec 無し）だけで dispatch が 0 で終わり、hook が通す。ほかは dispatch が 0 以外で state.json を変えず、hook が deny する |
| R2 | 手元で実物 | 手元の一時のディレクトリに新しい空の git repo を作り、tmux の中で `claude --plugin-dir <この worktree>/plugins/spec-autopilot --model claude-sonnet-5-5` を起動し、前回の試走と同じ依頼文「/spec-autopilot:autopilot ブラウザで遊べるシンプルなテトリスのようなゲームを作りたい。基本の操作（移動・回転・落下・行の消去・スコア）だけでよい。自走の範囲は PR まで。GitHub に repo は作らない」を送り、入れ子の transcript の時刻と、試作の dispatch の時点の spec.md の大きさの行を読む | 試作の dispatch の時点で大きさが M で、（試作を開き方つきで示す main の文の時刻 − 送信の時刻）が 10 分以内。草案が S のまま試作を dispatch したら、その回は M の測りに数えず、同じ依頼文の末尾に「大きさは M で見積もってください」を足して 1 回だけ回し直す（回し直したことと S の回の時間も qa.md に書く） |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 脅威: 承認の前のコードの書き込みが既存の repo に広がること（判定を新しく作る repo の M に限り、既存の repo の M を拒むテストで守る）

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
- R2 の実測が 10 分を超えたとき（数字を添えて人に戻し、照合役と試作の並行などを相談する）
