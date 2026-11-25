# 大きさ S の spec で、承認の前に試作の実装役を起動できるようにする

- ADR: docs/adr/2026-11-24-s-prototype-before-approval.md

## 目的
`references/small-prototype.md` は、大きさ S の spec で承認の前に実装役に試作を書かせると定めているが、`overnight.py dispatch` と実装役の起動の hook（`hooks/agent_gate.py`）が phase=discovery を拒むので、手順どおりに試作を作れない（2026-11-24 の試走で、main は試作なしで草案を示した）。人が文より動くものを見て直しを出せるよう、S の試作を承認の前に作れるようにする。できあがったら、S の spec の草案に試作が付き、承認の前の S でない spec の実装は今までどおり止まる。

## 要件
- R1: phase が discovery で「## 制約」の大きさの行が `- 大きさ: S` の spec に、tasks.md にあるタスクで `overnight.py dispatch <dir> --task T<n>` を打ったとき、dispatch は最後の行に起動する実装役の名前を出して、終了コード 0 で終える。
- R2: phase が discovery で大きさが S でない（M・L、大きさの行が無い、形が読めない）spec に R1 の dispatch を打ったとき、dispatch は state.json を変えずに終了コード 0 以外で拒む。building の spec の dispatch の振る舞いは変えない。
- R3: phase が discovery で大きさが S の spec に R1 の dispatch を打った後、その dispatch が指した実装役を起動するとき、PreToolUse hook（`hooks/agent_gate.py`）は起動を通す。
- R4: phase が discovery で大きさが S でない spec の実装役の起動と、S でも dispatch を打っていない・dispatch が指したのと別の段の実装役の起動を、R3 の hook は deny する。phase が building の spec と、discovery・building でない phase の spec の判定は変えない。
- R5: 承認の前に R1 の dispatch を打ち、実装役がその後に commit した S の spec を承認し、そのタスクを tasks.md で [x] にしてから、同じタスクで `overnight.py handoff` を打ったとき、handoff はその dispatch を閉じて終了コード 0 で終える。
- R6: `references/small-prototype.md` は、試作の実装役を起動する前に、tasks.md に全要件を受け持つタスクを書いて（playbook のタスクがあればそれを先頭に）`overnight.py dispatch` を打つことと、承認の後に試作で済んだタスクを [x] にして handoff で閉じてから評価に進むことを書く。`overnight.py` の冒頭の使い方の dispatch の行と、`agent_gate.py` の docstring は、discovery の S の spec を受けることを書く。`plugin.json` の version を上げる。

## 非目標
- handoff を discovery で受けること（試作の後に評価役は回らず、承認の後に閉じれば足りる）
- 既存の repo で、申告の S と数えた大きさの食い違いを dispatch・hook で見ること（承認の lint が見る）
- `autopilot.py check` が qa.md の証拠のテスト名の中の `、`・`・` を区切りと読む不具合（別の spec にする）
- わざと避ける形（spec.md の大きさを書き換える、state.json を書き換える）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:669-683（cmd_dispatch）
  - メモ: 5 行目の冒頭の使い方の dispatch の行も直す
- 変える: plugins/spec-autopilot/hooks/agent_gate.py（全体）
  - メモ: problem の phase の判定と docstring だけ
- 変える: plugins/spec-autopilot/scripts/lineup.py:73-86（begin）
  - メモ: discovery からの承認で dispatches・handoffs を消さない
- 変える: plugins/spec-autopilot/references/small-prototype.md（全体）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version だけ
- 新規: plugins/spec-autopilot/tests/test_prototype_gate.py
- 呼び出し元: plugins/spec-autopilot/hooks/hooks.json:1-15
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1210-1220
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:46
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:960
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:159
- 手本: plugins/spec-autopilot/tests/test_agent_gate.py:1-60（hook に payload を stdin で渡す形）
- 手本: plugins/spec-autopilot/scripts/autopilot.py:524-535（stated_size。大きさの行の読み方）
- 同じ入力: dispatches
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_prototype_gate.py -q

## 変えない挙動
- dispatch の無い building の spec の起動を deny する: plugins/spec-autopilot/tests/test_agent_gate.py::test_gate_denies_an_implementer_when_no_dispatch_was_made
- handoff で閉じた後の起動を deny する: plugins/spec-autopilot/tests/test_agent_gate.py::test_gate_denies_after_the_dispatch_was_closed_by_a_handoff
- 別の段の実装役の起動を deny する: plugins/spec-autopilot/tests/test_agent_gate.py::test_gate_denies_an_implementer_of_another_rung

## 前提
- 目的に届く: hook と CLI の変更は、plugin を入れ直した後に始めたセッションでしか効かない。試作を作るかは、今までどおり main が small-prototype.md を読んで決める
- 運用: /autopilot の main が、S の草案で tasks.md を書いて dispatch → 実装役 → 承認 → handoff の順に打つ
- 普通のやり方: なし（この plugin に固有の手順の門で、外に同じ種類のものが無い）
- 過去: 実装役の起動の hook は、dispatch の打ち忘れを止めるために入れた（docs/specs/2026-11-23-handoff-after-close）。そのとき S の試作の道は考えに入っていなかった（その spec の要件と非目標に試作の語が無い）
- 前提: dispatch は phase が building でないと拒む
  - path: plugins/spec-autopilot/scripts/overnight.py:669-675（cmd_dispatch）
  - コマンド: `一時の repo で autopilot.py init の後に tasks.md に T1 を書き、overnight.py dispatch <dir> --task T1` → 「dispatch は自走中（building）だけ受ける（phase=discovery）」で exit 1
- 前提: 実装役の起動の hook は phase が building でない spec を deny する
  - path: plugins/spec-autopilot/hooks/agent_gate.py:81-96（problem）
  - コマンド: `同じ spec を prompt に書いた Agent の PreToolUse の payload を agent_gate.py の stdin に渡す` → permissionDecision が deny で、理由は「building でない（discovery）」
- 前提: dispatch は tasks.md に無いタスクを拒む（init の tasks.md の雛形にはタスクの行が無い）
  - path: plugins/spec-autopilot/scripts/overnight.py:1077-1084（impl_name）
  - path: plugins/spec-autopilot/templates/tasks.md:1-3
- 前提: 承認（discovery からの approve と、queued の着手）は lineup.begin で dispatches・handoffs を含む ROUND_KEYS を state.json から消す。queued の着手は queued_from（discovery）を prev に渡す
  - path: plugins/spec-autopilot/scripts/lineup.py:73-86（begin）
  - path: plugins/spec-autopilot/scripts/overnight.py:53（ROUND_KEYS）
  - path: plugins/spec-autopilot/scripts/lineup.py:159
- 前提: 大きさの行は「## 制約」の `- 大きさ: <S|M|L>` の 1 行だけを受ける
  - path: plugins/spec-autopilot/scripts/autopilot.py:524-535（stated_size）
- 前提: handoff は phase が building でないと拒み、最後の dispatch が開いていれば、その base からの commit と、dispatch の後の実装役の起動の記録を確かめる
  - path: plugins/spec-autopilot/scripts/overnight.py:821-860（cmd_handoff）

## 作り方
この spec の ADR のとおり、dispatch と hook が受ける phase を「building、または discovery で大きさが S」に広げる。大きさは `autopilot.stated_size` で「## 制約」から読む。dispatch は今までどおり HEAD・タスク・実装役の名前を state.json の dispatches に記録し、hook は prompt に書かれた spec のうち、最後の dispatch が handoff で閉じておらず、その agent が起動する名前と同じものがあれば通す（phase の条件だけを広げる）。試作かどうかの印は持たない。承認（lineup.begin）は、prev が discovery のとき dispatches・handoffs を消さずに持ち越し、handoff は building のまま、承認の後に試作の dispatch を閉じる。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で S の spec を init し、tasks.md に T1 を書いて CLI の dispatch を打つ | base で落ち、tip で終了コード 0、state.json の dispatches に 1 件、最後の行が実装役の名前 |
| R2 | 手元で実物 | 大きさが M・L・行なし・形が読めない spec で同じ dispatch を打つ | どれも終了コード 0 以外で、state.json が変わらない |
| R3 | 手元で実物 | R1 の後に、spec を prompt に書いた Agent の PreToolUse の payload を agent_gate.py の stdin に渡す | base で deny、tip で出力が空で終了コード 0 |
| R4 | 手元で実物 | discovery の M の spec（dispatches を state.json に書いたもの）、dispatch の無い S の spec、別の段の名前で起動する payload を渡す。既存の test_agent_gate.py を回す | どれも deny で、既存のテストが通る |
| R5 | 手元で実物 | R1 の後に commit と実装役の起動の記録を作り、CLI の approve で承認し（`--queue` で承認して lineup.py next で着手する形も）、タスクを [x] にして CLI の handoff を打つ | base で落ち、tip でどちらも終了コード 0 で、state.json の handoffs がその dispatch を閉じる |
| R6 | 手元で実物 | 3 つの文書の該当の箇所と plugin.json を読む | 手順・使い方・docstring に discovery の S があり、version が 0.1.2 より上 |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: bug-fix
- 想定する脅威: 事故（S の試作の dispatch・起動が止められる、S でない spec で承認の前に実装役を起動する）。spec.md の大きさや state.json を書き換えて通す形は想定しない

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
