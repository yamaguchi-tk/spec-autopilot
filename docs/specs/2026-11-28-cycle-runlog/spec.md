# runlog.py を autopilot.py から外し、import の輪を 6 モジュールから 5 モジュールに縮める

- ADR: docs/adr/2026-11-28-cycle-runlog.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、2 本目を受け持つ。

観測: 1 本目（2026-11-28-cycle-deploy-stages）で deploy・preflight・stages が輪を出て、輪は autopilot・goal・light・lineup・overnight・runlog の 6 つ、循環の組は 15 になった。runlog.py が autopilot.py から借りている名前（COMMENT_BLOCK・section・stated_size・repo_root）のうち、stated_size のほかはもう stages.py にある。stated_size を stages.py にそのまま移すと、stages.py の中でどの関数ともつながらず、LCOM4 が 2 から 3 に上がって悪化になる。stages.py の repo_root と git_lines は、同じ形の git の呼び出しをそれぞれに書いていて、git_lines はどの関数ともつながっていない。

できあがったら、runlog.py は stages.py だけに依り、輪は autopilot・goal・light・lineup・overnight の 5 つに縮む。

## 要件
- R1: plugins/spec-autopilot/scripts を測ったとき、runlog.py は import の輪に入らず、輪は autopilot.py・goal.py・light.py・lineup.py・overnight.py の 5 つの 1 つだけで、循環の組は 15 から 10 に減る。
- R2: runlog.py を読んだとき、autopilot を import する文（関数の中の import と `__import__` を含む）と `autopilot.<名前>`・`ap.<名前>` の参照を持たず、輪を `importlib`・変数で名前を渡す `__import__`・`sys.modules` に替えて道具に見えなくする形も無い（文字列の中の `autopilot` の語は数えない）。
- R3: 測ったとき、stated_size を置く下の層のモジュールは、scripts のモジュールを carry.py のほかに import せず、LCOM4 が 2 以下になり、autopilot.py の fan-out は 16 を超えず、autopilot.py の LCOM4 は 4 を超えない。
- R4: 回帰テストと足したテストが通り、CLI の lint・check・status と、done・block が runs.jsonl に書く行を、変える前と後で同じ spec に回した出力が同じで、指標の前後の比べ方（着手の commit を前にする）で悪化が無く、「移しただけ」と出ない。テストは名前の向け先だけを変え、期待は変えない。

## 非目標
- goal・light・lineup・overnight・watch・hooks を autopilot.py から外すこと（後の子で扱う。それらは stated_size などを autopilot.py を通して使い続ける）
- premises.py・rootcause.py・size_note.py が受ける `sys.modules[__name__]` を直すこと（後の子で扱う）
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う。悪化だけを止める）
- 挙動・CLI の出力・エラー文・runs.jsonl の行を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 54 の SIZE_LINE・55 の SIZE_ANY と 511 の stated_size を stages.py に移し、autopilot.py はそこから import して使う
- 変える: plugins/spec-autopilot/scripts/stages.py（全体）
  - メモ: 39 の repo_root と 79 の git_lines が git を呼ぶ形を、同じモジュールの 1 つの関数にまとめて両方から呼ぶ。移した stated_size を持つ
- 変える: plugins/spec-autopilot/scripts/runlog.py（全体）
  - メモ: 35 の record の中の 37 の `import autopilot as ap` を stages の import に替える
- 呼び出し元: plugins/spec-autopilot/scripts/goal.py:21
  - メモ: runlog と autopilot を import する。goal.py は変えない
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:63
  - メモ: ap.stated_size を使う。lineup.py は変えない（ほかに light.py:167・overnight.py:324・size_note.py:12）
- 手本: plugins/spec-autopilot/scripts/carry.py:1-21（ほかの scripts を import しない小さいモジュール）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_import_layers.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_runlog.py plugins/spec-autopilot/tests/test_goal_done.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_watch.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_advisor_approval.py -q -n auto
  - メモ: 移す名前（stated_size・SIZE_LINE・SIZE_ANY・repo_root・git_lines）と stages・runlog・runs.jsonl を参照するテストと、autopilot を直接 import して autopilot.<名前> を使うテストのファイル。全量は CI が回す

## 変えない挙動
- QA の段の判定: plugins/spec-autopilot/tests/test_stages.py
- 大きさの数え方: plugins/spec-autopilot/tests/test_size.py
- runs.jsonl の記録: plugins/spec-autopilot/tests/test_runlog.py

## 前提
- 目的に届く: 輪は 6 から 5 モジュールに縮むが、0 にはならない。残りの goal・light・lineup・overnight と、premises・rootcause・size_note の `sys.modules[__name__]` と hooks は、後の子で向け直す。この子の間は、stated_size をほかのモジュールが autopilot.py を通して使い続ける（autopilot.py 自身も stated_size を使う）
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: import の輪は、共通の部分を下の層に出し、依存の向きを 1 つにそろえて切る。同じ形の外部の呼び出しは 1 つの関数にまとめる
  - メモ: 親の spec の普通のやり方の項と、この spec の ADR
- 過去: 1 本目の 2026-11-28-cycle-deploy-stages は、補助を stages.py に移して deploy・preflight・stages を輪から出した（PR 117）。新しいモジュールを足すと autopilot.py の fan-out が 16 から増えて悪化になるので、stages.py に寄せた
  - メモ: docs/adr/2026-11-28-cycle-deploy-stages.md
- 前提: 今の輪は autopilot・goal・light・lineup・overnight・runlog の 6 つで、循環の組は 15、stages.py の LCOM4 は 2（git_lines が孤立）、autopilot.py の fan-out は 16・LCOM4 は 4
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → 上の値（main の 8eb6d94 で測った）
- 前提: runlog.py が scripts から import するのは、record の中の autopilot だけで、使う名前は COMMENT_BLOCK・section・stated_size・repo_root
  - path: plugins/spec-autopilot/scripts/runlog.py:37（ほかに 41・42・43・53）
- 前提: stages.py の repo_root と git_lines は、どちらも `subprocess.run(["git", ...], cwd=..., capture_output=True, text=True)` で git を呼ぶ
  - path: plugins/spec-autopilot/scripts/stages.py:41（ほかに 81）
- 前提: git の呼び出しを 1 つの関数にまとめ、stated_size を stages.py に移すと、stages.py の LCOM4 は 2、autopilot.py の LCOM4 は 4 のまま
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py <写しを直した scripts> --json` → stages.py の塊は stated_size と残りの 2、autopilot.py は 4

## 作り方
この spec の ADR のとおり、stated_size と SIZE_LINE・SIZE_ANY を stages.py に移し、runlog.py は stages.py を import して使う。stages.py の repo_root と git_lines は、git を呼ぶ 1 つの関数（引数は cwd と git の引数）を同じモジュールに足して両方から呼ぶ（呼ぶ git の引数・capture_output・text・cwd は今と同じにし、repo_root の OSError の扱いと git_lines の終了コードの扱いはそれぞれに残す）。autopilot.py は stated_size を stages.py から import する。ほかのモジュールが autopilot.stated_size で使うのは、この子では向け直さない。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、輪と循環の組を読む | 輪が 5 モジュールの 1 つで、runlog が入らず、循環の組が 10 |
| R2 | 手元で実物 | runlog.py を `import autopilot`・`autopilot\.[A-Za-z_]`・`ap\.[A-Za-z_]`・`importlib`・`sys.modules`・`__import__` で grep する | grep が 0 件（文字列の中の語は除く） |
| R3 | 手元で実物 | stated_size を置いたモジュールの import を読み、指標の前後の比べ方でそのモジュールの LCOM4 と autopilot.py の fan-out・LCOM4 を読む | carry.py のほかに scripts を import せず、LCOM4 が 2 以下、autopilot.py の fan-out が 16 以下、LCOM4 が 4 以下 |
| R4 | 手元で実物 | 回帰テストと足したテストを回し、着手の commit と tip で同じ spec に CLI の lint・check・status を回し、一時の SPEC_AUTOPILOT_HOME で done・block の runs.jsonl の行を書かせて突き合わせ、指標の前後の比べ方を回す | 全部通り、出力と行が同じ（時刻を除く）で、悪化 0、「移しただけ」と出ない |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。import 先と git の呼び出しの置き場だけを変えるので、回帰テストで守る）

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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
- 指標の前後の比べ方で悪化が出て、直すと別の指標が悪化するとき（その要件を park に積み、朝の報告に書く）
