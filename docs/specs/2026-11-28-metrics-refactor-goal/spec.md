# spec-autopilot の scripts を、行数でなく複雑さ・凝集度・結合度の指標で測って、挙動を変えずに良くする

- ADR: docs/adr/2026-11-28-metrics-refactor-goal.md

## 目的
人の発言（順に）:「リファクタは完了した？」「行数以外のソフトウェアメトリクスでは？」「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「最初にリファクタリングして その後に機能追加を実施して」「スキルを作り終わったら / 5案を先に進めて / その後にリファクタで良い」「リファクタの spec」。

観測: 前のリファクタ（2026-11-26-split-modules）は行数で分けただけで、指標で測ると、20 を超える複雑度の関数の数も重複も変わらず、互いに import し合う組は増え、autopilot.py の凝集度は下がった（移しただけ）。今の plugins/spec-autopilot/scripts は、複雑度 20 を超える関数が 18 本、deploy.py の LCOM4 が 5、8 つのモジュールが 1 つの import の輪になっている。

できあがったら、spec-autopilot に行を足す改善を、複雑な関数と import の輪に足さずに始められる。リファクタの spec は、行数でなく指標の前後で良くなったかを確かめられる。挙動・CLI の出力・エラー文は変わらない。

## 要件
- R1: リファクタの spec を書くとき、/autopilot の playbook に refactor があり、それを選んだ spec は、変える前の指標の値を前提に書き、QA の方向性の合格基準を「指標の前後の比べ方で悪化が無く、狙った指標が目標の値に届き、移しただけでない」にする。
- R2: plugins/spec-autopilot/scripts を測ったとき、循環的複雑度が 20 を超える関数は 0 本になり、変える前に 20 を超えていた関数で値が上がったものは無い。
- R3: plugins/spec-autopilot/scripts を測ったとき、変える前に LCOM4 が 4 以上だったモジュール（deploy.py・advisor_approval.py・ladder.py と、R4 の子のマージの後に測り直して 4 以上の autopilot.py）と、それを分けた先のモジュールの LCOM4 は 2 以下になる。
- R4: plugins/spec-autopilot/scripts を測ったとき、互いに import し合うモジュールの輪は無く、依存の向きは autopilot.py（CLI の入口）→ 各モジュール → 下の層の 1 つになる。輪を `importlib`・変数で名前を渡す `__import__`・モジュールごとを渡す引数（`sys.modules[__name__]` など）に替えて道具に見えなくする形と、下の層に出した名前を autopilot.py 経由で使い続ける出し直し（re-export）は無い。
- R5: R2〜R4 のどの子をマージした後も、テストの全量が通り、CLI の出力とエラー文は変わらず、指標の前後の比べ方で悪化は無く、「移しただけ」と出ない。テストは名前の向け先だけを変え、期待は変えない。

## 非目標
- 挙動・CLI の出力・エラー文を変えること
- hooks/ と tests/ を指標で直すこと（hooks は Stop hook の時間の上限があり、別の spec で扱う。テストは利用者の規則の対象外）
- `~/.claude/rules/code-health.md` を直すこと（repo の外の利用者の規則で、人が別に決める）
- 版数を上げること（挙動を変えないので、R1 の playbook だけを、マージの後に版数だけの PR で届ける）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: R2 の lint（593）・impact（429）・check（690）・evidence_problem（805）、R4 の関数の中の import（`import` と `__import__("…")` の 15 行と、970 の `import advisor_approval, goal, lineup`）。子を作る時点の行番号で書き直す
- 変える: plugins/spec-autopilot/scripts/overnight.py（全体）
  - メモ: R2 の report（711）・cmd_await（247）・input_kinds（59）・cmd_handoff（507）・launch_errors（432）・impl_name（782）・cmd_rolled_back（657）
- 変える: plugins/spec-autopilot/scripts/deploy.py（全体）
  - メモ: R2 の production（322）・scope_lint（103）・scope_errors（173）と、R3 の分け方
- 変える: plugins/spec-autopilot/scripts/transcript.py（全体）
  - メモ: R2 の anomalies（70）
- 変える: plugins/spec-autopilot/scripts/ladder.py（全体）
  - メモ: R2 の report_lines（125）と、R3 の分け方
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
  - メモ: R3 の分け方
- 変える: plugins/spec-autopilot/scripts/watch.py（全体）
  - メモ: R2 の tick_one（250）
- 変える: plugins/spec-autopilot/scripts/stages.py（全体）
  - メモ: R2 の check（154）
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: R1 の playbook の索引の表に 1 行
- 新規: plugins/spec-autopilot/references/playbooks/refactor.md
- 変える: plugins/spec-autopilot/tests/test_playbooks.py（全体）
  - メモ: R1。期待するファイルの一覧に refactor を足し、「ファイルの無い名前」の例の refactor を別の名前に替える
- 変える: plugins/spec-autopilot/scripts/lineup.py（全体）
  - メモ: R3・R4。40・119・149・283・332-333 で deploy・overnight を関数の中で import する
- 変える: plugins/spec-autopilot/scripts/light.py（全体）
  - メモ: R3・R4。115・154 で deploy・lineup を関数の中で import する
- 変える: plugins/spec-autopilot/scripts/preflight.py（全体）
  - メモ: R3・R4。53・132 で deploy を関数の中で import する
- 変える: plugins/spec-autopilot/scripts/goal.py（全体）
  - メモ: R4。21 で autopilot を import する
- 変える: plugins/spec-autopilot/scripts/runlog.py（全体）
  - メモ: R4。37 で autopilot を関数の中で import する
- 新規: plugins/spec-autopilot/scripts/common.py
  - メモ: R4 で、輪の中のモジュールが autopilot.py から使う名前を出す下の層の候補。名前と置き場は子 3 で確定する。R3 で deploy.py から分けるモジュールも子 4 で確定する
- 呼び出し元: plugins/spec-autopilot/scripts/watch.py:250
  - メモ: tick_one が deploy を引数で受ける。R3 で名前の置き場が変わるなら向け直す
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:73
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:213
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:417-428
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:473
  - メモ: autopilot・deploy・transcript を import する。R3・R4 で名前の置き場が変わるなら向け直す
- 手本: plugins/spec-autopilot/scripts/carry.py:1-21（ほかの scripts を import しない小さいモジュール）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/ -q -n auto
  - メモ: tests/ の 36 本は、どれも変えるモジュール（autopilot・overnight・deploy・transcript・ladder・watch・stages・playbooks・lineup・light・preflight・goal・runlog）のどれかを参照するので、全量を回す

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- Stop hook の走査は予算を過ぎたら止める側に倒れる: plugins/spec-autopilot/tests/test_stop_bounds.py
- 自走の異常の数え方と出力: plugins/spec-autopilot/tests/test_anomalies.py
- マージ・デプロイ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py

## 前提
- 目的に届く: R2〜R4 で、行を足す改善の多くが当たる関数（lint・check・report）と、import の輪の中心の autopilot.py が軽くなる。複雑度 20 以下の 51 本の警告の関数は残る。LCOM4 は 4 以上を直し、overnight.py の 3 は残す（autopilot.py は R4 で塊が変わるので、R4 の後の値で入れる）。fan-out は入口の autopilot.py だけが高く、目標にしないが悪化させない
- 運用: 指標は repo の外の測る道具（lizard を土台にした refactor-metrics の skill）で測る。道具は repo に入れない。評価役は、手元にある道具で前と後を測る。道具の無い人は、R1 の playbook の合格基準を、lizard などで同じ形に測る
- 普通のやり方: 複雑度の高い関数は、早期 return と条件の塊の抽出で下げる。LCOM4 の高いモジュールは、つながりの塊ごとに分ける。import の輪は、共通の部分を下の層に出し、依存の向きを 1 つにそろえる
  - メモ: lizard（https://github.com/terryyin/lizard）の README の指標の説明と、測る skill の直し方の表
- 過去: 2026-11-26-split-modules は行数で transcript.py と deploy.py を切り出したが、指標で測ると複雑度・重複は変わらず、import の輪は増えた。この spec は前後の指標で合否を決める
  - メモ: docs/specs/2026-11-26-split-modules/spec.md の要件は行数だけで書かれている
- 前提: 今の scripts は、関数 317 本・複雑度の平均 7.50・20 を超える関数 18 本・10 を超える関数 69 本・重複の塊 2（0.92%）・import の輪 1（8 モジュール）
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts` → 上の値（main の 06a73a8 で測った）
- 前提: LCOM4 は deploy.py が 5、autopilot.py・advisor_approval.py・ladder.py が 4、overnight.py が 3
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → modules の lcom4
- 前提: import の輪は autopilot.py・deploy.py・goal.py・light.py・lineup.py・overnight.py・preflight.py・runlog.py の 8 つで、autopilot.py が関数の中で、輪の中のモジュールを `import` か `__import__("…")` で 16 か所 import している
  - コマンド: `grep -nE '^\s+import (deploy|goal|light|lineup|overnight|preflight|runlog)\b|__import__\("(deploy|goal|light|lineup|overnight|preflight|runlog)"\)' plugins/spec-autopilot/scripts/autopilot.py` → 15 行（ほかに 970 の `import advisor_approval, goal, lineup`）
- 前提: autopilot.py は `sys.modules[__name__]` を 5 か所で premises・stages・rootcause・size_note に渡していて、道具の import の輪には数えられない同じ向きの依存になっている
  - path: plugins/spec-autopilot/scripts/autopilot.py:623（ほかに 650・653・1022・1041）
- 前提: fan-out は autopilot.py の 16 だけが目安の高（15）を超え、ほかは overnight.py の 6 以下。関数の長さ（60 行超）は 4 本、ネストの深さ（4 超）は 1 本、引数の数（5 超）は 4 本
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → modules の fan_out と functions の nloc・nesting・params
- 前提: lint は走っている scripts の隣の references/playbooks/ を読むので、R1 のマージの後も、手元の plugin を人が更新するまでは子の spec に `- playbook: refactor` を書けない
  - path: plugins/spec-autopilot/scripts/playbooks.py:5
  - path: CLAUDE.md:19（手元の checkout の pull は人が頼んだときだけ）
- 前提: refactor の playbook はまだ無い
  - path: plugins/spec-autopilot/references/playbooks/feature.md（ほかに bug-fix・external-service・iac だけ）

## 作り方
この spec の ADR のとおり、目的の spec として 1 回承認し、要件ごとに子を 1 本ずつ、R1 → R4 → R2 → R3 の順に回す。子 2〜4 の spec は `- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）` で書き、合格基準は R1 の playbook と同じ形にする。R5 は R2〜R4 の子の全部が受け持つ。子は main から順にブランチを切り、前の子のマージの後に、その時点の行番号で書く。子の承認は相談役と検証役の経路（`approve --queue --by-advisor`）で通す。

- 子 1（R1）: playbook の refactor.md を、既存の playbook と同じ 3 節（spec を書くとき・自走のタスク・評価役の観点）で足し、索引と test_playbooks.py を直す。playbook には道具の名前もパスも書かない
- 普通のやり方の項目ごとの扱い: 複雑度の早期 return・条件の塊の抽出・分岐の表（dict）への置き換えは子 2 で扱う。関数の長さ（nloc）と引数の数（params）は、複雑度を下げる抽出で一緒に下がる分だけを扱い、目標にしない。LCOM4 の塊ごとの分割は子 4 で扱う。import の輪の、共通の部分を下の層に出す・依存の向きをそろえる・呼び出しを引数で渡すは子 3 で扱う。重複（塊 2・0.92%）は範囲外
- 子 2（R4）: 輪の中のモジュールが autopilot.py から借りている補助（spec の文の読み取り・state・repo の場所など）を、役ごとの下の層のモジュールに出し、各モジュールはそこを直接 import する。autopilot.py の関数の中の import と `sys.modules[__name__]` の 5 か所は、下の層の import に直す。呼び出しを引数で渡すのは関数を渡す場合に限る。下の層に出したモジュールの LCOM4 を測り、2 を超えるなら役ごとに分ける。`ap.`・`autopilot.` の参照は scripts の 17 ファイルに 212 か所あり、M に収まらなければ子を分ける。R2 より先に回す（autopilot.py の lint は関数の中の import を 9 か所持ち、R2 と同じ行を書き換えるため。autopilot.py は 1500 行の目安まで 114 行しかない）
- 子 3（R2）: 子の spec の要件は関数を名指しして書く。複雑度の高い順に、早期 return・条件の塊の抽出・分岐の表で下げる。M に収まらなければ子を 2 本に分ける（autopilot.py と、ほかのファイル）
- 子 4（R3）: R4 の後に LCOM4 を測り直し、4 以上のモジュールを、つながりの塊ごとに分ける。塊が 1 つの関数だけなら、分けずに置き場を移す。分けた先の LCOM4 と輪が悪化しないことも確かめる

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | playbook のテストを回し、`CLI lint` を `- playbook: refactor` の spec に回す | テストが通り、lint が refactor を受け、refactor.md に道具の名前とパスが無い |
| R2 | 手元で実物 | 子の着手の commit を前にして、指標の前後の比べ方を回す | 20 を超える関数が 0 本（park に積んだ関数を除く）、悪化 0、移しただけでない |
| R3 | 手元で実物 | 同じく前後の比べ方を回し、対象のモジュールと分けた先の LCOM4 を読む | 対象と分けた先の LCOM4 が 2 以下、悪化 0 |
| R4 | 手元で実物 | 同じく前後の比べ方を回し、輪の数を読む。scripts を `importlib`・`sys.modules`・変数の `__import__` と、下の層の名前を autopilot.py に出し直す行で grep する | 輪が 0、grep が 0 件、悪化 0 |
| R5 | 手元で実物 | テストの全量を回し、CLI の check・lint・report を前と後で同じ spec に回して出力を突き合わせる | 全部通り、出力が同じ |

## 制約
- 予算: 330 分
- 大きさ: L
- playbook: なし（挙動を変えないリファクタで、refactor の playbook は R1 で作る）
- 想定する脅威: なし（hook と判定の結果を変えない。判定の関数の中を書き換えるので、変えない挙動のテストの全量で守る）

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
- 子の前後の比べ方で悪化が出て、直すと別の指標が悪化するとき（その子を discovery に残し、朝の報告に書く）
- R2 の子で、ある関数を 20 以下に下げる直し方が無いと分かったとき（早期 return・条件の塊の抽出・分岐の表のどれでも、出力かエラー文が変わるか、別の指標が悪化する）: その関数は変えずに残し、関数の名前・前の値・試した直し方と結果を park に積む。ほかの関数は進める。park に積んだ関数が 1 本でも残る間は、R2 を満たしたと数えず、親を done にせず、朝の報告で人に 1 通で示す
