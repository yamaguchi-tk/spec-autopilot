# 要件の high で、落ちた入力の種類を表にしてテストにさせる

- ADR: docs/adr/2026-11-25-input-kinds-table.md

## 目的
人の問い:「根本的な解決方法を自動で選択するにはどうするのがいいか？」「セッションが進んでHITLになると対処療法的なものが増えてくる」。

観測した失敗は docs/specs/2026-11-23-handoff-after-close の R3 である。レビューの high が 4 巡続いた（state.json の reviews）。巡ごとに、指摘された spec のパスの形を 1 つずつ足す直しだった（docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md の Context）。実装役の定義には「指摘の入力は例として扱い、同じ判定を通る入力の全部で成り立つように直す」という文がもうあるが、文だけでは効かなかった。

できあがったら、要件が high を受けた巡で、評価役が落ちた入力と同じ処理を通るほかの種類の入力を表にする。その要件の直しは、表がなければ実装役に渡せない。表の行ごとにテストが無ければ、直しを閉じられない。表の行に fail が残る間は、完了の検査が通らない。

3 本に分けた spec の 2 本目である（1 本目の requirement-how-check と 3 本目の fix-order-park はマージ済み）。

## 要件
- R1: 最後のレビューで high を受けた要件を受け持つタスクを `overnight.py dispatch <dir> --task T<n>` で渡すとき、spec のディレクトリの `inputs/R<n>.md` に、見出しが `| 入力の種類 | 例 | 期待 | 今の結果 | テスト |` の表が無いか、データの行が 2 行未満か、入力の種類・例・期待の欄が空の行があるか、今の結果が `pass`・`fail` 以外の行があるか、今の結果が `fail` の行が 1 つも無いときは（ファイルが `- 入力の種類: なし（<理由>）` の行だけのときを除く）、dispatch は記録せずに 0 以外の終了コードで終わり、足りないものとファイルのパスを出す。
- R2: R1 の要件を受け持つ dispatch を `overnight.py handoff` で閉じるとき、`inputs/R<n>.md` の行のうち、テストの欄が qa.md の pass の証拠と同じ書き方の `<path>::<テスト名>` でない行か、書いたテストが repo に無い行があれば、handoff は閉じずに 0 以外の終了コードで終わり、その行を出す。
- R3: `autopilot.py check` は、park に積んでいない要件の `inputs/R<n>.md` に今の結果が `fail` の行があれば、その要件と行を挙げ、評価役を回し直して今の結果を書き換えさせると書いて落ちる。
- R4: 評価役は、要件に high を返すとき、`inputs/R<n>.md` に R1 の表を書く（落ちた入力の行と、同じ処理を通るほかの種類の入力の行を 1 行以上。前の巡の表があれば、行を足し、各行の今の結果をその巡で確かめた結果に書き換える）。high が入力の形で落ちたものでない（テストが無い・変異が生き残ったなど）ときは、表の代わりに `- 入力の種類: なし（<理由>）` の 1 行を書く。high を返さない要件でも、表があれば各行の今の結果を確かめ直して書き換える。
- R5: R1 で dispatch が通ったときの出力は、表のパスと、実装役に表の行ごとにテストを書かせ、テストの欄を埋めさせることを書く。
- R6: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.4 から 0.1.5 に上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 入力の種類が足りているか（同じ処理を通る種類を全部挙げたか）を CLI で判定すること（行の数と形だけを見る。中身は評価役が書き、次の巡の評価役が読む）
- `autopilot.py fail --from impl`（実装役が満たせなかった報告）で表を求めること
- 実装役の定義と commands/autopilot.md を変えること（main への指示は dispatch と check の出力で渡す）
- テストの欄のテストが、その行の入力を本当に確かめているかを CLI で判定すること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:678-694（cmd_dispatch）
- 変える: plugins/spec-autopilot/scripts/overnight.py:832-872（cmd_handoff）
- 変える: plugins/spec-autopilot/scripts/overnight.py:436-448（review_errors）
  - メモ: check が読む。R3 の fail の行の検査をここから返す
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-fable.md（全体）
  - メモ: 3 つの本文は同じ（tests/test_ladder.py の test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 新規: plugins/spec-autopilot/tests/test_input_kinds.py
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:720
  - メモ: check が review_errors を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1223
  - メモ: dispatch・handoff の subparser
- 手本: plugins/spec-autopilot/scripts/autopilot.py:769-790（evidence_problem。qa.md の pass の証拠のテストが repo にあるかを見る）
- 手本: plugins/spec-autopilot/tests/test_ladder.py:15-40（high を記録して dispatch する道具）
- 同じ入力: inputs、reviews、parked
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_input_kinds.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto
  - メモ: high の後に dispatch するテストは test_ladder.py・test_autopilot.py にある。表を置く道具を足して直す

## 変えない挙動
- high の無い巡の後の dispatch は今までどおり通る: plugins/spec-autopilot/tests/test_ladder.py::test_park_names_only_the_requirement_past_the_top_and_the_rest_goes_on
- 実装役の失敗で段を上げる: plugins/spec-autopilot/tests/test_ladder.py::test_a_failure_of_the_implementer_raises_its_requirement_at_once
- 閉じた後に main が書いたコードを handoff が拒む: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_refuses_code_written_by_main_after_close
- 3 つの評価役の本文が同じ: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body

## 前提
- 目的に届く: 届くのは、high の後の直しの前に入力の種類を 2 つ以上書かせ、行ごとのテストを直しの閉じる条件にするところまで。挙げた種類が足りているかは評価役の読みに頼り、CLI は数と形しか見ない。観測した失敗は handoff-after-close の R3 の 1 本で、ほかの spec での効き目は測っていない
- 運用: /autopilot の main が評価役の high を受けたら、評価役が書いた `inputs/R<n>.md` があることを dispatch で確かめ、dispatch の出力に従って実装役に表を渡す。high がすべて `確かめ方: 再実行` で main が回し直して通した巡（commands/autopilot.md:93）では、表の今の結果を書き換える評価役が走らないので、R3 の check が落ち、そのエラーに従って評価役を回し直す。変更が効くのは、マージの後に人が plugin の checkout を pull してから（repo の CLAUDE.md の規則）
- 普通のやり方: 1 つの失敗した入力から、同じ処理を通る入力をまとめて分け、分けた組ごとにテストを書く（同値分割。pytest の parametrize で組ごとに 1 件を並べる形。https://docs.pytest.org/en/stable/how-to/parametrize.html）
- 過去: docs/specs/2026-11-23-handoff-after-close/state.json の reviews で R3 の high 4 巡を確かめた。docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md の Context に、巡ごとにパスの形を足した経緯がある
- 前提: dispatch はタスクの要件と段を記録し、最後の行に起動する agent の名前を出す
  - path: plugins/spec-autopilot/scripts/overnight.py:678-694
- 前提: handoff は誤りがあれば閉じずに report で返す
  - path: plugins/spec-autopilot/scripts/overnight.py:832-872
- 前提: check は review_errors の返す誤りで落ちる
  - path: plugins/spec-autopilot/scripts/autopilot.py:720
- 前提: 最後のレビューの high は state.json の reviews の最後の項目の high にある
  - path: plugins/spec-autopilot/scripts/autopilot.py:1215-1245
- 前提: 実装役の定義には、指摘の入力を例として扱えという文がもうある
  - path: plugins/spec-autopilot/agents/autopilot-implementer.md:9
- 前提: 評価役には Write の tool があるが、書いてよい先を `.autopilot-qa/` と spec の `evidence/` に限っている。R4 で `inputs/` を足す
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:6
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:9

## 作り方
この spec の ADR のとおり、表の検査を overnight.py の dispatch・handoff と、check が読む review_errors に置く。

- 評価役の定義: agents/autopilot-reviewer.md・autopilot-reviewer-xhigh.md・autopilot-reviewer-fable.md の本文に同じ文を足す（:9 の書いてよい先に `inputs/` を足す）
- main への指示: commands/autopilot.md は変えない（変えると変えるファイルが 6 つになり、大きさが L になる）。high の後の直しで表を渡すことは dispatch の出力（R5）が、再実行の巡で評価役を回し直すことは check の出力（R3）が言う
- 表の置き場: spec のディレクトリの `inputs/R<n>.md`。spec のファイルなので、approve の検査と handoff の「main が spec の外に書いた」の検査の外にある
- テストの欄: qa.md の pass の証拠と同じ書き方にし、autopilot.py の evidence_problem でテストの有無を見る。評価役が high のときに書く行のテストの欄は `-` でよい（R1 は見ず、R2 で実装役が埋める）
- 表の検査の本体は、overnight.py に 1 つの関数として置く（autopilot.py は 1498 行で、触らない）
- park に積んだ要件: state.json の parked に `req` が R<n> の項目がある要件
- 既存のテストのうち high の後に dispatch するものは、表を置く道具を足して直す（新しい約束に合わせる）
- 文書の語があるかを assert するテストは書かない。評価役の定義の変更は、QA で評価役の 1 巡の出力を読んで確かめる

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で `review --high R1` を記録した後、表が無い・行が 1 行・欄が空・今の結果が別の語・fail の行が無い・`- 入力の種類: なし（<理由>）` の行だけ・揃った表で `overnight.py dispatch` を打ち、state.json を読む | 揃った表と、なしの行だけのファイルで dispatch が記録される。ほかは終了コードが 0 以外で、足りないものとパスを出し、dispatches が増えない。high の無い巡の後の dispatch は表が無くても通る |
| R2 | 手元で実物 | R1 の一時の repo で、テストの欄が `-`・無いテスト・ある test の node id の表で、commit してから `overnight.py handoff` を打つ | 全行が repo にあるテストのときだけ閉じる。ほかは終了コードが 0 以外で、その行を出し、handoffs が増えない |
| R3 | 手元で実物 | R2 の後に `review --high none` を記録し、表に fail の行を残したまま・全部 pass・fail を残してその要件を park に積んだ、の 3 つで `autopilot.py check` を打つ | fail を残して積んでいないときだけ、その要件と行を挙げ、評価役を回し直すと書いて落ちる |
| R4 | 手元で実物 | 一時の repo で、入力の形で落ちる小さい実装の spec に評価役を 1 回起動する（`claude -p --plugin-dir <worktree>/plugins/spec-autopilot --agent <評価役の名前>`）。3 つの評価役の定義の本文を読む | high の要件に `inputs/R<n>.md` があり、R1 の検査を通る（2 行以上・fail が 1 行以上）。3 つの本文が同じで、表の書き方と、入力の形でない high の `- 入力の種類: なし（<理由>）` の書き方がある |
| R5 | 手元で実物 | R1 の揃った表で dispatch を打った出力を読む | 表のパスと、行ごとにテストを書かせテストの欄を埋めさせる旨がある |
| R6 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が 0.1.5 で、テストが通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 脅威: 想定するのは事故（評価役が表を書き忘れる、実装役が指摘の形だけを直してテストを書かない）で、わざと避ける形（中身の無い行で表を埋める）は見ない
- autopilot.py を変えない（1498 行で、利用者の規則の目安の 1500 行に近い）

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
