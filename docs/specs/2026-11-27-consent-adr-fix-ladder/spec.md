# 合意の ADR でも、直し方の 4 段で枠組みを変えた案を比べさせる

- ADR: docs/adr/2026-11-27-consent-adr-fix-ladder.md

## 目的
人の言葉:「目的に対して手段が最善か？ 枠組み変えたらもっと良い方法がある　みたいな視点がない」。

今は、枠組みを変える問い（直し方の 4 段: 要らなくする・入力の約束を変える・設計を変える・局所の継ぎ足し）が、同じ要件で 3 巡失敗した後の作り直しにしか出ない。作り方を決める合意の段の ADR は、同じ枠の中の局所の違い（どの条件で分岐するか）だけを並べがちで、docs/adr の 26 本のうち段の行を持つのは作り直しの 1 本だけである。

できあがると、合意の段の ADR が、選んだ段より上の段（たとえば「そもそも要らなくできないか」）を退けた理由を必ず持ち、行が無ければ承認に進めず、書いた本人でない照合役がその理由を目的に当てて読む。人は承認のときに、枠組みを変えた案が比べられたかを ADR の数行で見られる。

## 要件
- R1: phase が discovery か queued の spec に `CLI lint` を回したとき、spec の先頭の `- ADR:` が指すファイルに `- 直し方: <段>` の行がちょうど 1 本無いか、選んだ段より上の段のどれかに `- 退けた: <段>（<理由>）` か `- 要件の文で退けた: <段>（R<n> の「<要件の語>」）` の行が無ければ、lint は ERROR を返し、足りない行をすべて挙げる。
- R2: R1 の ERROR がある spec では、合意ありの承認（`CLI approve`、`--queue` を含む）と軽量フローの承認（`light.py approve`）は通らない。
- R3: R1 の行がそろった ADR に `- 要件の文で退けた:` の行があるとき、lint はその行で ERROR にせず、行ごとに、退けた段と要件の番号と語を含む NOTE を返し、park のコマンドは出さない。
- R4: phase が building・blocked・done・wait の spec と、目的の spec の承認（`CLI approve --goal` と、それが回す lint）では、ADR に R1 の行が無くても、`CLI lint`・`CLI check`・block と done の後の `CLI approve`（合意し直し）は、R1 の検査で ERROR を出さない。
- R5: spec の先頭に `- ADR:` が無いか、指すファイルが無いとき、lint は R1 の ERROR を出さず、approve は今の「ADR が無い」の文で止まる。
- R6: 作り直し（`CLI rework`）の入口の判定と文は、今のまま変わらない。
- R7: `references/adr-template.md` の段の行の例（`<段>`・`<理由>`・`R<n>`・`<要件の語>` を埋めたもの）を合意の ADR に書くと、R1 の検査を通る。雛形は、段の行を作り直しの ADR だけに限らない。
- R8: 照合役（`agents/autopilot-spec-checker.md`）に、ADR の `- 退けた:`・`- 要件の文で退けた:` の理由を「## 目的」に当てる項目を足す。理由が、その段で目的に届かない訳（「要らなくする」なら、既存の機能・手順・設定で目的に届かない訳）を書いていなければ、照合役はその行ごとに `ng` を返す。「合意し直し」と渡されたときは、この項目を `該当なし（合意し直し）` にする。
- R9: `commands/autopilot.md` の A の 1 と A の 4 は、作り方の案を、4 段の上の段（要らなくする・入力の約束を変える）から先に考え、選んだ段より上の段を退けた理由を ADR に書くよう、能動的に求める。B の 4 は、人に示すものに、ADR の直し方の段と、上の段を退けた行を入れる。

## 非目標
- 版数を上げること（CLAUDE.md の振り分け 1 として、別の PR にする）
- `/autopilot` を通らない直し（CLAUDE.md の振り分け 2）で、枠組みを問うこと（観測が 1 件だけなので、先に件数を測る）
- 小さい直しで `/autopilot` を速くすること（CLAUDE.md の最後の項の、最初の 5 本の runs.jsonl で決める）
- 退けた理由の中身を CLI で判定すること（形だけを見る。中身は照合役と人が読む）
- 既にある ADR に段の行を書き足すこと

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/rootcause.py:15-31（check）
  - メモ: 合意の ADR を見る関数を足し、check を使う。refuse_if_unfit は変えない
- 変える: plugins/spec-autopilot/scripts/autopilot.py:620-621（lint）
  - メモ: phase が discovery・queued のときだけ、rootcause の新しい関数を呼ぶ。このファイルは 1500 行を超えているので、行数を増やさない
- 変える: plugins/spec-autopilot/references/adr-template.md:27-30（全体）
- 変える: plugins/spec-autopilot/commands/autopilot.md:43-76（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-spec-checker.md:9-22（全体）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:962
  - メモ: cmd_approve が lint を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:160
  - メモ: 軽量フローの approve が lint を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:46-57
  - メモ: queue_lint が lint を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:159
  - メモ: queued の spec の着手（start）が lint を呼び、通らなければ block にする
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1296
  - メモ: rework が refuse_if_unfit を呼ぶ
- 手本: plugins/spec-autopilot/tests/test_rootcause.py（rework の入口で段の行を確かめるテスト）
- 別の実装: plugins/spec-autopilot/scripts/rootcause.py:34-44
  - メモ: 同じ段の行を読む refuse_if_unfit（rework の入口）。変えない
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_rootcause.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_main_progress.py -q -n auto

## 変えない挙動
- rework は直し方の行が無い・読めない・2 本ある ADR を断る: plugins/spec-autopilot/tests/test_rootcause.py::test_rework_refuses_missing_unknown_or_duplicate_fix_line
- rework は上の段の退けた行が欠けた ADR を断り、欠けた段を挙げる: plugins/spec-autopilot/tests/test_rootcause.py::test_rework_names_the_missing_rejected_stage
- 段の正本は FIX_ORDER の 4 段で、この順: plugins/spec-autopilot/tests/test_rootcause.py::test_fix_order_is_the_four_stages_in_order
- 雛形の行の例は rootcause が読む形に合う: plugins/spec-autopilot/tests/test_rootcause.py::test_documented_line_examples_match_the_shapes_rootcause_reads
- 雛形は 4 段を FIX_ORDER の順に並べる: plugins/spec-autopilot/tests/test_rootcause.py::test_adr_template_lists_fix_stages_in_fix_order

## 前提
- 目的に届く: 合意の段の ADR に、枠組みを変えた段を退けた理由が必ず残り、照合役と人が読む。退けた理由を形だけ埋めた ADR は CLI を通る。軽量フローは照合役を通らないので、そこでは形だけになる。`/autopilot` を通らない直しには効かない
- 運用: main が合意の ADR を書くときに段の行を書き、lint が足りない行を挙げる。効いたかは、導入後の合意の ADR で、選んだ段が「局所の継ぎ足し」より上だった本数と、照合役の新しい項目の ng の数で見る（導入前の値: docs/adr の 26 本のうち、行頭の段の行を持つのは作り直しの 1 本）
- 普通のやり方: ADR の「Considered Options」に、問題を消す案（何もしない・既存のもので済ませる）を含める（MADR の雛形。URL: https://adr.github.io/madr/）。この repo では、作り直しの ADR の 4 段がそれに当たる
- 過去: PR 25 で作り直しの ADR に段の行を求め、PR 16 で照合役が要件の中の作り方を止めるようにした。どちらも合意の段の ADR の選択肢の枠は見ていない（`gh pr list --state all --search "rootcause OR 直し方"` で確かめた）
- 前提: 段の行の形は rootcause.check が読み、足りない行の一覧と、要件の文で退けた行の park のコマンドを返す。終わらせはしない
  - path: plugins/spec-autopilot/scripts/rootcause.py:15-31（check）
- 前提: refuse_if_unfit は「rework:」で始まる文で終わり、要件の文で退けた行があると park を促して終えるので、承認にはそのまま使えない
  - path: plugins/spec-autopilot/scripts/rootcause.py:34-44（refuse_if_unfit）
- 前提: lint は spec の phase を読んでおり、初回の合意（discovery・queued）で、目的の spec の承認（--goal）でないときだけ効く検査（first_agreement）を既に持つ。R1 も同じ条件にする（目的の spec の子は、それぞれの ADR で R1 を通る）
  - path: plugins/spec-autopilot/scripts/autopilot.py:620（first_agreement）
- 前提: queued の spec の着手は、lint を回し、通らなければ block にする
  - path: plugins/spec-autopilot/scripts/lineup.py:159-162（start）
- 前提: 合意ありの承認・`--queue` の承認・軽量フローの承認は、どれも lint を通る
  - path: plugins/spec-autopilot/scripts/autopilot.py:962（cmd_approve）、plugins/spec-autopilot/scripts/lineup.py:46-57（queue_lint）、plugins/spec-autopilot/scripts/light.py:160（cmd_approve）
- 前提: 自走中の check は ADR のファイルがあるかだけを見て、lint を呼ばない
  - path: plugins/spec-autopilot/scripts/autopilot.py:693-695（check）
- 前提: 雛形は段の行を作り直しの ADR だけに限っている
  - path: plugins/spec-autopilot/references/adr-template.md:27
- 前提: テストの共通の雛形の ADR（`# ADR: canvas で描く` の 1 行）は段の行を持たないので、R1 を入れると lint・approve を通すテストが落ちる。雛形の ADR に段の行を足して直す
  - path: plugins/spec-autopilot/tests/test_autopilot.py:129（init_spec）、plugins/spec-autopilot/tests/test_main_progress.py:159、plugins/spec-autopilot/tests/test_light.py:293
- 前提: 照合役の出力の表は、どのスクリプトも読まない
  - コマンド: `grep -rn "spec-checker\|spec_checker" plugins/spec-autopilot/scripts plugins/spec-autopilot/hooks` → 当たりなし

## 作り方
この spec の ADR のとおり（直し方の段は「入力の約束を変える」）。合意の ADR が満たす約束に段の行を足す。形は lint が rootcause.check で見て（初回の合意のときだけ。lint を通る 3 つの承認すべてに効く）、意味は照合役の新しい項目で目的に当てる。rootcause.py に、ADR の本文から (ERROR の一覧, NOTE の一覧) を返す関数を足し、autopilot.py の lint からは 1 行で呼ぶ（autopilot.py の行数を増やさない）。雛形・autopilot.md の A の 1 と A の 4・照合役の表を同じ変更で直す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で spec を init し、段の行が無い・直し方が 2 本・上の段の退けた行が 1 つ欠ける ADR で `CLI lint` を回す | どれも終了コードが 0 でなく、足りない行がすべて出る。行がそろうと通る |
| R2 | 手元で実物 | R1 の ERROR がある spec で、人の発言を記録してから `CLI approve`・`CLI approve --queue`・`light.py approve` を回す | 3 つとも通らず、phase が discovery のまま |
| R3 | 手元で実物 | `- 要件の文で退けた:` の行を持つ ADR で `CLI lint` を回す | 終了コードが 0 で、NOTE に段・要件の番号・語が出て、park のコマンドが出ない |
| R4 | 手元で実物 | 段の行の無い ADR を持つ spec を承認した状態（building）と done・blocked にして、`CLI lint`・`CLI check`・合意し直しの `CLI approve` を回す。discovery の L の spec で `CLI approve --goal` を回す | どれも R1 の ERROR が出ない |
| R5 | 手元で実物 | `- ADR:` の無い spec と、指すファイルの無い spec で `CLI lint` と `CLI approve` を回す | lint に R1 の ERROR が出ず、approve は「ADR が無い」の文で止まる |
| R6 | 手元で実物 | test_rootcause.py を base と tip で回す | 両方で通り、rework のテストの期待の文を変えていない |
| R7 | 手元で実物 | tip の adr-template.md の段の行の例を埋めた ADR で `CLI lint` を回す。雛形のコメントを読む | lint に R1 の ERROR が出ない。コメントが段の行を作り直しの ADR だけに限っていない |
| R8 | 手元で実物 | tip の照合役の定義を読み、新しい項目を docs/adr/2026-11-26-night-notes-short-run.md（段の行が無い）と、この spec の ADR に当てる | 新しい項目があり、合意し直しで該当なしになる。前者に段の行が無い ng、後者の退けた理由に ok を出せる書き方である |
| R9 | 手元で実物 | tip の autopilot.md の A の 1・A の 4・B の 4 を読む | A の 1 と A の 4 が、上の段から先に案を考え、退けた理由を ADR に書くことを、見つけたら言う形でなく求める形で書いている。B の 4 の示すものに、直し方の段と退けた行がある |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 想定する脅威: 判定を変える spec。悪意のある入力ではなく、main が段の行を形だけ埋めて通す事故を想定する（CLI では止めず、照合役と人が読む）。止める側に倒すので、正当な初回の合意が段の行を書けば通ること、自走中の spec を止めないことを守る

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
