# 承認の前に、照合役が要件の中の作り方を止める

- ADR: docs/adr/2026-11-24-requirement-how-check.md

## 目的
人の問い:「根本的な解決方法を自動で選択するにはどうするのがいいか？」「セッションが進んでHITLになると対処療法的なものが増えてくる」。

観測した失敗は docs/specs/2026-11-23-handoff-after-close の R3 である。レビューの high が 4 巡続いた（state.json の reviews）。作り直しの ADR（docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md）は、根本の案「prompt を読まない」を「要件が変わる」として退けた。要件 R1 が「prompt に書かれた spec のディレクトリ」と入力の取り方を決めていたためである。

できあがったら、作り方を決めた要件は承認の前に照合役に止められ、作り方の節へ移る。自走中の作り直しで、根本の案が要件の文に締め出されなくなる。

3 本に分けた spec の 1 本目である。ほかの 2 本は、入力の種類の表（input-kinds-table）と、直し方の順位（root-cause-fix-order）。

## 要件
- R1: autopilot-spec-checker が spec を照合するとき、照合役は項目 10「要件の中の作り方」として、要件の文が目的と合格基準に要らない仕組み（入力の取り方・データの形・使う道具や API・判定の手順）を決めている要件ごとに `ng` の行を返し、根拠にその語と「作り方の節へ移す」を書く。
- R2: R1 の照合で、外から見える約束（利用者・ほかのプログラムが頼る形。hooks.json に登録する tool の matcher、CLI の引数の形など）を書いた要件は `ng` にしない。
- R3: 照合役は「合意し直し」と渡されたときも項目 10 を見る。commands/autopilot.md の合意し直しの照合の項は、照合役が見る項目に 10 を足して書く。
- R4: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.1 から 0.1.2 に上げ、marketplace の description は plugin.json と同じに保つ（入れた人の checkout が pull した後に、照合役の変更が届くように）。

## 非目標
- 要件の中の作り方を `CLI lint` で機械的に見つけること（語の一覧では、外から見える約束と見分けられない）
- 承認の後に、agent が要件の文を書き換えて緩めること（承認のハッシュは要件の節を守っている）
- 承認済みの spec に作り方が残っていたときの出口（root-cause-fix-order の spec で扱う）

## 影響範囲
- 変える: plugins/spec-autopilot/agents/autopilot-spec-checker.md（全体）
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 115 行目の合意し直しの照合の項だけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:73
  - メモ: B の 3 が照合役を起動する
- 手本: plugins/spec-autopilot/agents/autopilot-spec-checker.md:18（項目 8 の、目的に照らす書き方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q
  - メモ: 照合役の定義を参照するテストは無い（文書の語の有無を見るテストは repo の規則で書かない）。R1〜R3 は QA の実物の照合で確かめ、このテストは commands と manifest の形を守る

## 変えない挙動
- commands が指すファイルがある: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_referenced_files_exist

## 前提
- 目的に届く: 届くのは新しい spec の承認の前まで。照合役の判定は LLM の読みなので、取りこぼしと誤った ng は残る（QA で 2 本の spec に当てて測る）。観測した失敗は Issue #2 の 1 本だけで、ほかの spec での頻度は測っていない
- 運用: /autopilot の main が B の 3 で照合役を起動し、返った ng を直してから人に示す（今の手順のまま）。変更が効くのは、マージの後に、自走中のセッションが無いときに人が plugin の checkout を pull してから（repo の CLAUDE.md の規則。pull は自走の範囲に入れない）
- 普通のやり方: 要件（何を満たすか）と設計（どう作るか）を分けて書く。GitHub Spec Kit は spec を what と why に限り、how を plan に分ける（https://github.com/github/spec-kit/blob/main/spec-driven.md）
- 過去: docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md の退けた案（「要件が変わる」で根本の案を退けた）。docs/specs/2026-11-23-handoff-after-close/state.json の reviews で R3 の high 4 巡を確かめた
- 前提: 照合役は 9 項目の表で照合し、合意し直しでは 5・7・8・9 を見る
  - path: plugins/spec-autopilot/agents/autopilot-spec-checker.md:9-28
  - path: plugins/spec-autopilot/commands/autopilot.md:115
- 前提: main は照合役の ng のうち、照合役が書いた検索か path:line を読み直して同じものだけを採る
  - path: plugins/spec-autopilot/commands/autopilot.md:73
- 前提: claude は --print と --agent と --plugin-dir を受ける
  - コマンド: `claude --help` → --agent・--plugin-dir・-p/--print がある
  - 未確認: plugin の agent の名前を --agent に渡せるかは、QA で実物で確かめる

## 作り方
この spec の ADR のとおり、照合役の表に項目 10 を足す。

- 判定の基準: 「目的と合格基準を満たすのに、その語が要るか」とし、外から見える約束の例を添える
- 合意し直し: 見る項目の並びに 10 を足す
- ng の行: 「確かめた方法」に要件の行の path:line を書く（main が読み直して採れるように）
- 普通のやり方の資料（Spec Kit の spec-driven.md）との対応: 扱うのは「spec に how を書かず、what と why に限る」の 1 点だけ。plan・tasks・constitution の gate など、ほかの手順は範囲外（この plugin には作り方の節・tasks.md・照合役が別にある）

文書の語があるかを assert するテストは書かない（repo の規則）。確かめは、QA の実物の照合で行う。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo に docs/specs/2026-11-23-handoff-after-close の spec.md を写し、`claude -p --plugin-dir <worktree>/plugins/spec-autopilot --agent <照合役の名前>` で照合役を 1 回回す | 項目 10 に R1 の `ng` の行があり、根拠に「prompt」の語と「作り方の節へ移す」がある |
| R2 | 手元で実物 | R1 と同じ 1 回の出力と、docs/specs/2026-11-24-advise-stray-space の spec.md を写して同じく 1 回回した出力を読む | handoff-after-close の R8 は、項目 10 で `ng` にならない。advise-stray-space では、項目 10 の `ng` が 0 件 |
| R3 | 手元で実物 | R1 の一時の repo で、prompt に「合意し直し」を足して照合役を 1 回回す。commands/autopilot.md の合意し直しの照合の項を読む | 項目 1〜4・6 は `該当なし（合意し直し）` で、項目 10 に R1 の `ng` の行がある。項の文が、見る項目に 10 を含む |
| R4 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が 0.1.2 で、テストが通る |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: feature
- 脅威: なし（照合役の文の変更で、hook と判定のコードは変えない）

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
