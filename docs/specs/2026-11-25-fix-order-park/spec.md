# 作り直しで、直し方の順位を書かせ、要件の文に締め出された直しを park に回す

- ADR: docs/adr/2026-11-25-fix-order-park.md

## 目的
人の問い:「根本的な解決方法を自動で選択するにはどうするのがいいか？」「セッションが進んでHITLになると対処療法的なものが増えてくる」。

観測した失敗は 2 つある。

- docs/specs/2026-11-23-handoff-after-close の R3 では、レビューの high が 4 巡続いた（state.json の reviews）。作り直しの ADR（docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md）は、根本の案「prompt を読まない」を「要件が変わる」として退け、パスの形を足す局所の直しを続けた
- docs/specs/2026-11-24-requirement-how-check の R1 では、失敗が 2 巡続いた後の直しが、前の直しを強める継ぎ足しだった（docs/adr/2026-11-24-checker-ground-column.md）

できあがったら、作り直しの ADR は、選んだ直し方の段と、それより上の段を退けた理由を書かないと記録できない。上の段を退けた理由が要件の文なら、作り直しを記録せず、その要件を park に積む。人は朝の報告で、要件の文を直すかを決める。

3 本に分けた spec の 3 本目である（1 本目は requirement-how-check で、マージ済み）。Issue #18 もここで閉じる。

## 要件
- R1: `autopilot.py rework <dir> --req R<n> --adr <ADR>` を打ったとき、ADR に `- 直し方: <段>` の行（段は「要らなくする」「入力の約束を変える」「設計を変える」「局所の継ぎ足し」のどれか）がちょうど 1 本無いか、選んだ段より上の段ごとに `- 退けた: <段>（<理由>）` か `- 要件の文で退けた: <段>（R<n> の「<要件の語>」）` の行が無ければ、rework は記録せずに 0 以外の終了コードで終わり、足りない行を出す。
- R2: R1 の ADR に `- 要件の文で退けた: <段>（R<n> の「<要件の語>」）` の行が 1 本以上あるとき、rework は記録せずに 0 以外の終了コードで終わり、行ごとに、その要件を積む `overnight.py park <dir> --kind other --op <要件の文を直す> --reason <退けた段と要件の語と ADR のパス> --req R<n>` のコマンドを、そのままシェルに貼って打てる形（引数はシェルの引用符で包む）で出す。
- R3: `autopilot.py check` は、park に積んだ要件について、失敗が 3 巡続いたことによる作り直しと block を求めない。
- R4: `autopilot.py check` が「spec.md の要件・QA の方向性・制約などが承認の後に変わった」を出すとき、そのエラー文は、spec.md を承認の時点に戻すこと、1 つの要件だけを変える必要があるなら `overnight.py park` で積むこと、どの要件も進められないときだけ block することを書く。
- R5: references/dead-end.md の 2 と references/adr-template.md は、R1 の 4 つの段を R1 と同じ順に書き、`- 直し方:`・`- 退けた:`・`- 要件の文で退けた:` の行の書き方を書く。dead-end.md の 2 の手順 3 と、rework が記録できたときの出力は、作り直しで tasks.md を直すときも 1 の手順 4 の `  - メモ: 前提:` の行を残すと書く。dead-end.md の 3 の park の条件に、R2 で rework が拒まれたときを書く。
- R6: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.3 から 0.1.4 に上げ、marketplace の description は plugin.json と同じに保つ。
- R7: 変更の後も plugins/spec-autopilot/scripts/autopilot.py は 1500 行以内である。

## 非目標
- 入力の種類の表を、最初の high で求めること（2 本目の spec input-kinds-table で扱う）
- 承認の後に、agent が要件の文を書き換えて緩めること（承認のハッシュは要件の節を守っている）
- 退けた理由の中身が正しいかを CLI で判定すること（行の有無と形だけを見る。中身は評価役と朝の報告で人が読む）
- 作り直しを 2 回した要件を block でなく park に回すこと（今の check は block を求める。dead-end.md の 3 との食い違いは別の課題）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1252-1275（cmd_rework）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:657-725（check）
  - メモ: 663-665 行目のエラー文だけ
- 変える: plugins/spec-autopilot/scripts/autopilot.py:727-744（ladder_errors）
- 新規: plugins/spec-autopilot/scripts/rootcause.py
- 新規: plugins/spec-autopilot/tests/test_rootcause.py
- 変える: plugins/spec-autopilot/tests/test_autopilot.py:1395-1397（new_adr）
  - メモ: rework が通る前提のテストの ADR に、R1 の行を足す
- 変える: plugins/spec-autopilot/references/dead-end.md（全体）
- 変える: plugins/spec-autopilot/references/adr-template.md（全体）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1484-1487
  - メモ: rework の subparser。check は Stop hook と CLI check から呼ばれる
- 手本: plugins/spec-autopilot/scripts/ladder.py:1-40（autopilot.py から import する小さい module）
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1395-1409（new_adr と test_rework_needs_new_existing_adr_and_resets_count）
- 同じ入力: reworks、parked、streak
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_main_progress.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q
  - メモ: test_main_progress.py は R4 で変える check のエラー文の一部（「承認の後に変わった」）を assert している

## 変えない挙動
- 3 巡に届く前の rework を拒む: plugins/spec-autopilot/tests/test_autopilot.py::test_rework_refused_before_third_fail
- 使った ADR の別名を拒む: plugins/spec-autopilot/tests/test_autopilot.py::test_rework_rejects_an_alias_of_a_used_adr
- 3 回目の rework を拒み block を指す: plugins/spec-autopilot/tests/test_autopilot.py::test_third_rework_is_refused_and_points_to_block
- 作り直しが要る間は Stop hook が止める: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_blocks_while_rework_is_required

## 前提
- 目的に届く: 届くのは、作り直しの ADR に直し方の段と退けた理由を書かせ、要件の文に締め出された直しを人に届けるところまで。CLI が見るのは行の形だけで、「上の段を本当に考えたか」は見ない（形だけ埋めた行は通る）。観測した失敗は 2 本で、ほかの spec での頻度は測っていない
- 運用: /autopilot の main が作り直しの ADR を書き、rework が拒んだら出たコマンドで park に積む。人は朝の報告の park を読み、要件の文を直すなら合意し直す。変更が効くのは、マージの後に人が plugin の checkout を pull してから（repo の CLAUDE.md の規則）
- 普通のやり方: 直しは、症状の場所でなく、システムが最初に誤った場所で行い、ガードの追加は守る状態が正しいときだけ直しとみなす（pstack の fix-root-causes。https://github.com/backnotprop/pstack）
- 過去: docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md の退けた案（「要件が変わる」で根本の案を退けた）と、docs/adr/2026-11-24-checker-ground-column.md（継ぎ足しの後の作り直し）。Issue #18（作り直しで前提のメモを消さない）
- 前提: rework は 3 巡に届いた要件だけを受け、新しい ADR を求め、作り直しは要件ごとに 2 回まで
  - path: plugins/spec-autopilot/scripts/autopilot.py:1252-1275
- 前提: check は、失敗が 3 巡続いた要件に、park の有無を見ずに作り直しか block を求める
  - path: plugins/spec-autopilot/scripts/autopilot.py:735-743
- 前提: check のエラー文は、承認の後に要件が変わったとき block を指す
  - path: plugins/spec-autopilot/scripts/autopilot.py:663-665
- 前提: park は自走中だけ受け、--kind other・--op・--reason・--req を取り、parked に req を書く
  - path: plugins/spec-autopilot/scripts/overnight.py:1007-1023
  - path: plugins/spec-autopilot/scripts/overnight.py:1216-1221
- 前提: check は、最後のレビューに high が 1 件でもあれば、park の有無を見ずに落ちる。park した要件は、main が次の review の --high に挙げないので、その review が none なら落ちない
  - path: plugins/spec-autopilot/scripts/autopilot.py:733-734
- 前提: autopilot.py は今 1498 行
  - コマンド: `wc -l plugins/spec-autopilot/scripts/autopilot.py` → 1498

## 作り方
この spec の ADR のとおり、rework の入口で ADR の行を読む。

- 置き場: ADR を読む検査の本体は、新しい scripts/rootcause.py に置く（autopilot.py を 1500 行以内に保つため）
- park に積んだ要件: state.json の parked に `req` が R<n> の項目がある要件とする
- scripts/rootcause.py に、段の並び `FIX_ORDER`（要らなくする・入力の約束を変える・設計を変える・局所の継ぎ足し）と、ADR の本文から足りない行と park のコマンドを返す関数を置く。autopilot.py の cmd_rework は呼ぶだけにする
- check の ladder_errors は、parked の req を外して数える
- README.md:25 の rework の説明（新しい ADR で作り方を変えるまで check が落ちる）は、この変更の後も正しいので変えない。直し方の段と park の書き方は、README が指す dead-end.md に書く
- 文書の段の並びは、FIX_ORDER と dead-end.md・adr-template.md を突き合わせるテストで確かめる（語の有無だけを見るテストは書かない）
- 既存のテストの `new_adr` は、R1 の行を持つ ADR を書くように直す（rework が通る前提のテストを、新しい約束に合わせる）
- autopilot.py が 1500 行を超えるなら、同じ PR の中で、挙動を変えない別の commit で行を減らす

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で 3 巡 high を記録した要件に、直し方の行が無い・段の名前が違う・2 本ある・上の段の退けた行が足りない・揃った ADR で `autopilot.py rework` を打ち、state.json を読む | 揃った ADR だけが記録される。ほかは終了コードが 0 以外で足りない行を出し、reworks が増えない |
| R2 | 手元で実物 | R1 の一時の repo で、`- 要件の文で退けた:` の行がある ADR で rework を打ち、出たコマンドをそのまま打つ | rework は終了コードが 0 以外で reworks が増えない。要件の語に `"`・`$(`・空白を含めても、出た park のコマンドがそのまま通り、parked に要件と理由が入る |
| R3 | 手元で実物 | R2 で積んだ後に `autopilot.py check` を打つ | 積んだ要件に作り直しと block を求めるエラーが出ない。積んだ要件を挙げずに `review --high none` を記録した後は、最後のレビューの high のエラーも出ない。積んでいない別の要件が 3 巡続いたときは、今までどおり作り直しを求める |
| R4 | 手元で実物 | 承認の後に spec.md の要件を 1 文変えた一時の repo で `autopilot.py check` を打つ | エラー文に、戻すこと・park・block の使い分けがある |
| R5 | 手元で実物 | FIX_ORDER と dead-end.md・adr-template.md の段の並びを突き合わせるテストを回す。R1 の揃った ADR で rework を打った出力を読む | 2 つの文書とも、4 つの段が FIX_ORDER と同じ順に出て、3 種の行の形が rootcause.py の読む形と同じ。rework の出力に前提のメモの行を残すとある |
| R6 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が 0.1.4 で、テストが通る |
| R7 | 手元で実物 | `wc -l plugins/spec-autopilot/scripts/autopilot.py` と、`python3 -m pytest plugins/spec-autopilot/tests/ -q` | 1500 行以内で、全部通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 脅威: 想定するのは事故（agent が直し方の段を飛ばす、上の段を書かずに局所の直しを選ぶ）で、わざと避ける形（中身の無い理由で行を埋める）は見ない
- autopilot.py を 1500 行より長くしない（利用者の規則の目安）

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
