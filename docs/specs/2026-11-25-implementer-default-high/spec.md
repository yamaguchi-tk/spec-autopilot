# 実装役の既定を Sonnet の effort high にする

- ADR: docs/adr/2026-11-25-implementer-default-high.md

## 目的
人の問い:「実装がSonnet lowなのが実装がいまいちな原因なのでは？」。人の決定:「規定もHighに変えて良い」。

観測した失敗: この repo の 5 本の spec（requirement-how-check・s-prototype-gate・evidence-name-separators・fix-order-park・input-kinds-table）の state.json で、実装役の dispatch の直後のレビューに、その要件の high が出たのは、既定の Sonnet low で 16 回中 9 回、sonnet-high で 4 回中 1 回、opus-medium で 1 回中 0 回だった。high 1 回で、評価役と直しの 1 巡（30〜50 分）が増え、5 本中 4 本が予算を超えた。

できあがったら、`## モデル` に実装の行を書かない spec の実装役は、始めから Sonnet 5.5 の effort high で動く。

## 要件
- R1: `## モデル` に `- 実装:` の行が無い spec で `overnight.py dispatch` か `overnight.py agent --role impl` を打ったとき、出す実装役の名前は `autopilot-implementer` で、その agent の定義は model が `claude-sonnet-5-5`、effort が `high` である。
- R2: 実装役の段は、下から `sonnet-high`・`opus-medium`・`opus-xhigh`・`fable` の順に上がる。`## モデル` に `- 実装: sonnet-low` と書いた spec は、`autopilot.py lint` が受ける段の名前を挙げて ERROR にする。
- R3: plugins/spec-autopilot/templates/spec.md の `## モデル` の注記は、R1 の既定と R2 の段の並びを書く。
- R4: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.5 から 0.1.6 に上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 評価役の既定（opus-high）を変えること
- 実装役の段を上げる条件（2 巡で原因調査、3 巡で作り直し）を変えること
- commands/autopilot.md の C の 2 にある、Sonnet low を既定にした計測の文を直すこと（commands の文書だけの直しなので、マージの後に pre-pr-review で別の PR にする）
- ほかの repo の承認済みの spec が `- 実装: sonnet-low` を書いていたときの読み替え（読み替えの分岐を足さず、lint の ERROR で知らせる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/ladder.py:9-16（RUNGS）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer.md（全体）
  - メモ: effort の行だけ
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-high.md（全体）
  - メモ: ファイルを消す
- 変える: plugins/spec-autopilot/templates/spec.md（全体）
  - メモ: 47 行目のモデルの節の注記だけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 変える: plugins/spec-autopilot/tests/test_overnight.py:822-826（test_handoff_refuses_an_effort_other_than_the_definition）
  - メモ: 定義の effort が low であることに頼る "low" の assert を "high" に直す
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:885
  - メモ: handoff が、起動した実装役の model と effort を agent の定義と突き合わせる
- 呼び出し元: plugins/spec-autopilot/hooks/agent_gate.py:107
- 手本: plugins/spec-autopilot/tests/test_ladder.py:199-211（段ごとに agent の定義の model と本文を見るテスト）
- 同じ入力: RUNGS、モデル
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto
  - メモ: test_ladder.py は段の名前と順を assert しているので、新しい並びに合わせて直す

## 変えない挙動
- 実装役の失敗で、その要件の段をすぐ 1 段上げる: plugins/spec-autopilot/tests/test_ladder.py::test_a_failure_of_the_implementer_raises_its_requirement_at_once
- Opus xhigh で 2 回落ちた後に Fable を 1 回だけ試す: plugins/spec-autopilot/tests/test_ladder.py::test_fable_comes_only_after_two_failures_at_the_top_opus_and_runs_once
- 段ごとの agent の定義の model と本文が揃う: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body

## 前提
- 目的に届く: 届くのは、既定の実装役を 1 段上げるところまで。比べた回数は少なく（sonnet-high は 4 回、opus-medium は 1 回）、上の段は原因調査の後の直しでしか使っていないので、指摘が揃った有利な条件で測っている。費用は Sonnet の effort high のぶん増える。効き目は、マージの後の spec の runs.jsonl（承認からの分数・high の巡の数）で測る
- 運用: 変更が効くのは、マージの後に、自走中のセッションが無いときに人が plugin の checkout を pull してから（repo の CLAUDE.md の規則）。自走中の spec の dispatch が `autopilot-implementer-high` を名指ししたまま pull すると、その agent の定義が無くなるので、pull は自走中のセッションが無いときに行う
- 普通のやり方: なし（モデルと effort の選び方に決まったやり方は無く、この repo の計測で決める）
- 過去: commands/autopilot.md の C の 2 に、Sonnet 5.5 low を既定にした計測（S の spec で Opus と fail が同じ 0 件、費用は約 1/4）がある。この repo の 5 本の state.json の dispatches と reviews で、上の目的の回数を数えた
- 前提: 実装役の段は RUNGS の impl の並びで、先頭が既定、順に上がる
  - path: plugins/spec-autopilot/scripts/ladder.py:9-16
  - path: plugins/spec-autopilot/scripts/ladder.py:60-75
- 前提: モデルの節の段の名前が RUNGS に無ければ、lint が受ける名前を挙げて ERROR にする
  - path: plugins/spec-autopilot/scripts/ladder.py:47-57
- 前提: hook と handoff は、名前が autopilot-implementer で始まる agent を実装役として扱う
  - path: plugins/spec-autopilot/hooks/agent_gate.py:107
  - path: plugins/spec-autopilot/scripts/overnight.py:885
- 前提: 既定の実装役の定義は model が claude-sonnet-5-5、effort が low
  - path: plugins/spec-autopilot/agents/autopilot-implementer.md:4-5

## 作り方
この spec の ADR のとおり、sonnet-low の段を消し、既定の agent の名前は `autopilot-implementer` のまま effort を high にする。

- RUNGS の impl は `sonnet-high`（`autopilot-implementer`、claude-sonnet-5-5、high）を先頭にし、`opus-medium`・`opus-xhigh`・`fable` を続ける
- agents/autopilot-implementer-high.md は消す（同じ model と effort の agent が 2 つ残らないように）
- 既定の agent の名前を変えないので、hook・handoff・commands・README が `autopilot-implementer` を既定とする書き方はそのまま正しい
- test_ladder.py の段の名前と順の assert は、新しい並びに合わせて直す（段の数が 1 つ減るので、park に届くまでの段の数も 1 つ減る）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で `## モデル` が空の spec を承認し、`overnight.py agent --role impl` と `overnight.py dispatch` を打つ。agents/autopilot-implementer.md の頭を読む | どちらも `autopilot-implementer` を出し、定義の model が claude-sonnet-5-5、effort が high |
| R2 | 手元で実物 | R1 の一時の repo で、同じ要件の high を記録して段を上げ続け、dispatch が出す名前を順に読む。`## モデル` に `- 実装: sonnet-low` と書いた spec で `autopilot.py lint` を打つ | 名前が autopilot-implementer → autopilot-implementer-opus → autopilot-implementer-opus-xhigh → autopilot-implementer-fable の順に出る。sonnet-low の spec は lint が受ける段の名前を挙げて ERROR になる |
| R3 | 手元で実物 | templates/spec.md の `## モデル` の注記を読み、RUNGS と突き合わせる | 注記の既定が sonnet-high で、段の並びが RUNGS の impl と同じ |
| R4 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が 0.1.6 で、テストが通る |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 脅威: なし（実装役の段の並びの変更で、hook と判定の条件は変えない）

## モデル
- 実装: sonnet-high

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
