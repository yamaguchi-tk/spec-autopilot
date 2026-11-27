# state.json に existing のキーが無いときは、既存の repo とみなす

- ADR: docs/adr/2026-11-27-existing-key-fail-closed.md

## 目的
人の決定:「先に spec で直す」。承認の前の試作の門は、state.json に existing のキーが無いと新しく作る repo とみなし、大きさ M の試作を承認の前に通してしまう（fail-open）。claude/leftover-lows の独立レビューが high として挙げ、PR 92 の評価役も low として挙げた。

できあがったら、キーが無い・値が bool の False でない state.json では、試作の門は M を拒み、lint と done も既存の repo として扱う。同じキーの読み方は 1 か所になる。この spec のマージの後に、claude/leftover-lows を PR にする。

## 要件
- R1: 承認の前（discovery）で、state.json に existing のキーが無いか、値が bool の false でなく（null・文字列・0 など）、spec の大きさの行が `- 大きさ: M` のとき、overnight.py dispatch は state.json を変えずに拒み、hooks/agent_gate.py は実装役の起動を拒む。existing が `false` の M は今と同じく通す。
- R2: state.json に existing のキーが無いか、値が bool の false でないとき、autopilot.py lint は既存の repo の節（「## 影響範囲」「## 変えない挙動」と回帰テストの行）を求め、autopilot.py done は既存の repo と同じく大きさを数える。existing が `false` の spec では今と同じく求めない。

## 非目標
- init がキーを書く挙動を変えること
- キーが無い state.json を読み込みでエラーにすること
- 試作の門の拒む文に、大きさの行が読めない理由を足すこと（独立レビューの advisory。別に扱う）
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:878-883（prototype_ok）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:623（lint）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1035（cmd_done）
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:891
- 呼び出し元: plugins/spec-autopilot/hooks/agent_gate.py:100
- 手本: plugins/spec-autopilot/tests/test_prototype_gate.py:63-70（試作を拒む表）
- 同じ入力: existing
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_size.py -q -n auto

## 変えない挙動
- 新しく作る repo の M の試作は通る: plugins/spec-autopilot/tests/test_prototype_gate.py::test_dispatch_in_discovery_accepts_a_medium_spec_in_a_new_repo_and_prints_the_implementer
- 既存の repo の S の試作は通る: plugins/spec-autopilot/tests/test_prototype_gate.py::test_dispatch_in_discovery_accepts_a_small_spec_in_an_existing_repo
- init は existing を記録する: plugins/spec-autopilot/tests/test_autopilot.py::test_init_records_whether_the_repo_already_has_code
- 既存の repo では lint が影響範囲と変えない挙動を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_lint_existing_repo_requires_impact_and_unchanged_behaviour

## 前提
- 目的に届く: 今の init はキーを必ず書くので、直るのはキーの無い state.json（手で作った・直したもの、古い版のもの）だけで、ふだんの流れの挙動は変わらない
- 運用: なし（hook と CLI の判定の直しで、人の手順は変わらない）
- 普通のやり方: なし（門の判定は、読めない・無い値を止める側に倒すのが普通で、この repo の prototype_ok も読めない spec.md を拒む）
- 過去: docs/specs/2026-11-27-new-repo-m-prototype（M の試作を新しく作る repo に限ったとき、キーの読み方を `not s.get("existing")` にした）
- 前提: キーが無いと、prototype_ok は M の試作を許す
  - コマンド: `python3 -c 'import sys, overnight; d=sys.argv[1]; print(overnight.prototype_ok(d, {"phase":"discovery"}), overnight.prototype_ok(d, {"phase":"discovery","existing":True}))' <一時のディレクトリ>` → `(True, None) (False, None)`
  - メモ: plugins/spec-autopilot/scripts で実行し、一時のディレクトリには「## 制約」に「- 大きさ: M」だけを書いた spec.md を置いた
  - path: plugins/spec-autopilot/scripts/overnight.py:878-883
- 前提: lint と done も、キーが無いと新しく作る repo とみなす
  - path: plugins/spec-autopilot/scripts/autopilot.py:623（lint）
  - path: plugins/spec-autopilot/scripts/autopilot.py:1035（cmd_done）
- 前提: init はキーを必ず書く
  - path: plugins/spec-autopilot/scripts/autopilot.py:895-899（cmd_init）
- 前提: overnight.py は 1510 行で、コード健全性の目安の 1500 行を超えている
  - コマンド: `wc -l plugins/spec-autopilot/scripts/overnight.py` → 1510
  - メモ: overnight.py の行は増やさない

## 作り方
この spec の ADR のとおり、autopilot.py に existing を読む関数を 1 つ置き（existing が `False` のときだけ新しく作る repo）、prototype_ok・lint・cmd_done がそれを使う。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、state.json から existing を消した M の spec と、existing を null・"false" にした M の spec を discovery に置き、overnight.py dispatch と hooks/agent_gate.py を入口から打つ。足したテストを base と tip で回す | base で落ち、tip で通る。tip では dispatch が 0 以外で state.json を変えず、hook が deny する。existing が false の M は通る |
| R2 | 手元で実物 | 一時の repo で、state.json から existing を消した spec と、existing を null にした spec に autopilot.py lint と done を打つ。足したテストを base と tip で回す | base で落ち、tip で通る。tip では lint が既存の repo の節を求める ERROR を出す |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: bug-fix
- 脅威: 事故（キーの無い state.json）だけ。敵対的に作った state.json は想定しない（state.json を書ける者は門を通さずにコードを書ける）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先: 手元の一時のディレクトリ（テストの一時の repo）
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
