# 大きさ S の草案を S の目安に収める

- ADR: docs/adr/2026-11-27-s-prototype-size.md

## 目的
人の言葉:「10分で終わらないのは時間かかりすぎ」「autopilot自体の改善か、試走のプロンプトの改善をして」。

観測した失敗は、ハンズオンの試走（2026-11-27、main と実装役は Sonnet 5.5、新しい repo）である。

- 依頼「ブラウザで遊べるテトリスのようなゲームを作りたい」: 要件 12 個に公式ガイドラインの細部（回転の壁蹴り、固定の猶予の回数、落下間隔の式など）が入った。試作の実装役は 8 分を超えても終わらず、本体 837 行・テスト 1,238 行を書いていた
- 依頼に「シンプル」「基本の操作だけでよい」を足した版: 要件はまた 12 個（S の上限）になった。本体 342 行（S の目安 200 行の 1.7 倍）・テスト 789 行で、送信から試作が示されるまで 10 分 41 秒かかった（この spec の fixtures/browser-tetris-spec.md）

実装役の時間は、ほぼ出力の生成で決まる（agents/autopilot-implementer.md の 2 の計測）。依頼文を絞っても、草案が S の上限まで埋まり、テストが本体の 2 倍を超えた。

できあがったら、S の草案は本体 200 行に収まる中身になり、収まらない草案は人に示す前に照合役に止められる。試作が早く示される。

2 本に分けた spec の 1 本目である。2 本目（s-prototype-tests）は、S の試作のテストを要件ごとに代表の数件にし、版数を上げる。

## 要件
- R1: feature の playbook で S の草案を書くとき、main は要件を本体（テストと docs を除く、足す行）200 行に収まる中身にし、要件の数を上限まで埋めず、その種類の公式のルールや資料の細部（ゲームなら回転の補正の表・固定の猶予の回数・落下の速さの式など）を要件に入れずに非目標の「足すなら」に挙げる。その種類のものに普通は付く機能（最高点の保存・画面に合う大きさなど）は、目安に収まる範囲で残す。
- R2: autopilot-spec-checker が「## 制約」に `- 大きさ: S` のある spec を照合するとき、照合役は項目 11「S の大きさ」として、要件を全部満たす本体（テストと docs を除く）が 200 行に収まるかを見積もり、収まらなければ、行を多く使う要件ごとに `ng` の行を返し、根拠に「非目標へ移す」か「大きさを M にする」を書く。収まるなら `ok` の行を 1 本返す。大きさが S でない spec では `該当なし` の行を 1 本返す。
- R3: 照合役は、新しく作る repo の spec と「合意し直し」と渡されたときも項目 11 を見る。

## 非目標
- 行数を lint や hook で機械的に見積もること（新しい repo には数える差分が無く、草案の文からは機械で数えられない）
- 試作の実装役が目安を超えたら途中で止める門（照合役と文言で再発が止まらなかったときに、実測を添えて別の spec にする）
- 試作のテストの数と版数（2 本目の spec）
- 起動から試作までの 10 分の実測を、この spec の QA で行うこと（入れ子の Claude Code の対話と権限の確認が要る。マージの後に、ハンズオンの手順書の試走で同じ依頼文・同じ model で測る）
- 照合役の起動・照合の指摘の反映・lint の書式エラーにかかる約 4 分の短縮

## 影響範囲
- 変える: plugins/spec-autopilot/references/playbooks/feature.md（全体）
  - メモ: 7 行目と 11 行目の、草案に入れる機能と上限の項
- 変える: plugins/spec-autopilot/agents/autopilot-spec-checker.md（全体）
  - メモ: 9 行目の見る項目の並びと、10 の後に項目 11 を足す
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 117 行目の合意し直しの照合の項だけ
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:75
  - メモ: B の 3 が照合役を起動する
- 手本: plugins/spec-autopilot/agents/autopilot-spec-checker.md:20（項目 10 の、ng の根拠に直し方を書く形）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_playbooks.py -q
  - メモ: 照合役と playbook の文を参照するテストは無い（文書の語の有無を見るテストは repo の規則で書かない）。R1〜R3 は QA の読み合わせと照合役の実物の照合で確かめ、このテストは commands・playbook の形を守る

## 変えない挙動
- commands が指すファイルがある: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_referenced_files_exist
- playbook はフォルダの中のファイル: plugins/spec-autopilot/tests/test_playbooks.py::test_the_playbooks_are_the_files_in_the_folder

## 前提
- 目的に届く: 届くのは草案と試作の中身まで。照合役の見積もりは LLM の読みなので、取りこぼしと誤った ng は残る。起動から試作までが 10 分に収まるかは、マージの後の試走でしか分からない（試走では、照合役の 1 本が 1 分 16 秒と 1 分 21 秒、照合の直しが約 1 分で、残りが試作の実装役だった）
- 運用: /autopilot の main が A の 2 で草案を書き、B の 3 で照合役を起動し、返った ng を直してから人に示す（今の手順のまま）。変更が効くのは、マージの後に、人が plugin の checkout を pull してから（repo の CLAUDE.md の規則。pull は自走の範囲に入れない）
- 普通のやり方: なし（spec の大きさを草案の段で見積もる仕組みの、決まった作り方は無い）
- 過去: docs/specs/2026-11-24-requirement-how-check（照合役に項目を足した前例。項目 10 を足し、合意し直しの照合の並びにも足した）
- 前提: 大きさ S の目安は、要件 12 個まで・変更 200 行まで
  - path: plugins/spec-autopilot/commands/autopilot.md:52
- 前提: feature の playbook は、草案に普通は付く機能と既定値を入れさせ、上限は要件の数だけを決めている
  - path: plugins/spec-autopilot/references/playbooks/feature.md:7、plugins/spec-autopilot/references/playbooks/feature.md:11
- 前提: 新しく作る repo では、大きさを表で決めて書き、lint は差分を数えない
  - path: plugins/spec-autopilot/commands/autopilot.md:58
- 前提: 照合役は S でも試作より先に回り、新しい repo では 1〜4 を該当なしにし、合意し直しでは 5・7・8・9・10 を見る
  - path: plugins/spec-autopilot/commands/autopilot.md:75、plugins/spec-autopilot/agents/autopilot-spec-checker.md:9、plugins/spec-autopilot/commands/autopilot.md:117
- 前提: 既存の repo の大きさの数え方は、テストと docs/ を除く
  - path: plugins/spec-autopilot/references/existing-repo.md:17
- 前提: claude は --print と --agent と --plugin-dir を受け、plugin の agent を --agent で回せる
  - path: docs/specs/2026-11-24-requirement-how-check/qa.md:6

## 作り方
この spec の ADR のとおり、草案を書く側（playbook）と、示す前に止める側（照合役）の文を直す。試作を書く側（実装役）は 2 本目の spec で直す。

- 本体の行の数え方は、既存の repo の数え方（テストと docs/ を除く）に合わせて「本体」と呼ぶ
- 照合役の定義の冒頭の見る項目の並び（新しい repo・合意し直し）と、commands/autopilot.md の合意し直しの照合の項に、11 を足す
- 照合役の項目 11 は、項目 10 と同じく、ng の行の根拠に直し方（「非目標へ移す」「大きさを M にする」）と path:line を書く

文書の語があるかを assert するテストは書かない（repo の規則）。確かめは、QA の読み合わせと照合役の実物の照合で行う。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 変えた feature.md を読む | S の草案について、本体 200 行に収める・上限まで埋めない・公式のルールの細部を非目標に回す・普通に付く機能は目安の範囲で残す、の 4 つが書かれている |
| R2 | 手元で実物 | 一時の repo に fixtures/browser-tetris-spec.md と fixtures/number-guess-spec.md をそれぞれ spec.md として置き、`claude -p --plugin-dir <worktree>/plugins/spec-autopilot --agent <照合役の名前>` で照合役を 1 回ずつ回す | browser-tetris では項目 11 に `ng` の行が 1 本以上あり、根拠に「非目標へ移す」か「大きさを M にする」がある。number-guess では項目 11 が `ok` |
| R3 | 手元で実物 | R2 の browser-tetris の一時の repo で、prompt に「合意し直し」を足して照合役を 1 回回す。照合役の定義の冒頭と commands/autopilot.md の合意し直しの照合の項を読む | 項目 1〜4・6 は `該当なし（合意し直し）` で、項目 11 に `ng` の行がある。2 つの文の見る項目に 11 が入っている |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: feature
- 脅威: なし（agent と playbook の文の変更で、hook と判定のコードは変えない）

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
