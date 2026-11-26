# 1 時間以内の run では夜通しの NOTE を出さない

- ADR: docs/adr/2026-11-26-night-notes-short-run.md

## 目的
体験会（予算 30 分の昼の run）で、初めての人に、関係の無い夜通し向けの NOTE（keep-awake・バッテリー・macOS の自動更新・見回り役）が出る。リハーサル 3 回とも lint と承認の出力に出て、agent が grep -v で隠すか「30 分の昼の作業には影響しない」と説明していた。見込みの終わりが 1 時間以内の run では出さず、夜通し回す run にだけ出す。

## 要件
- R1: 予算とマージ後の予算と、まとめて承認したときに前に並ぶ spec の予算の合計が 60 分以下の spec で `CLI lint` か `CLI approve` を実行したとき、出力は keep-awake・バッテリー・macOS の自動更新・見回り役の NOTE を含まない。
- R2: その合計が 60 分を超える spec か、予算が読めない spec で `CLI lint` か `CLI approve` を実行したとき、出力は今と同じく、当たる keep-awake・バッテリー・macOS の自動更新・見回り役の NOTE を含む。
- R3: 合計が 60 分以下の spec でも、`CLI lint` と `CLI approve` は今と同じく、AWS の SSO と GDD の lock の ERROR・NOTE を出す。

## 非目標
- NOTE の文言を変えること
- SSO・GDD の検査の条件を変えること
- 60 分の閾値を設定で変えられるようにすること
- commands/autopilot.md:75（承認で示す夜通しの前提の文）を直すこと。`.md` だけの直しなので、この repo の CLAUDE.md どおり pre-pr-review の別の PR にする

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/preflight.py（全体）
  - メモ: 変えるのは check（30〜44 行）だけ。名前が一般的で grep が無関係のファイルに当たるので全体で書く
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:619
- 変える: plugins/spec-autopilot/tests/test_rollback.py:609-617（test_lint_warns_when_nothing_keeps_the_mac_awake）
  - メモ: 819 行・825 行のバッテリーと自動インストールのテストも、予算 30 分の spec で NOTE が出ると確かめている。この 3 本は予算 90 分の spec に替えて R2 の側に移し、30 分で出ない側のテストを R1 に足す
- 手本: plugins/spec-autopilot/scripts/preflight.py:117-125（sso）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_watch.py plugins/spec-autopilot/tests/test_lineup.py -q

## 変えない挙動
- SSO が夜の終わりまでに切れる profile は承認で止める: plugins/spec-autopilot/tests/test_rollback.py::test_approve_refuses_an_aws_profile_whose_sso_session_ends_before_the_night
- GDD の lock が有効なら承認で止める: plugins/spec-autopilot/tests/test_rollback.py::test_approve_refuses_an_active_gdd_marker_when_a_settings_file_cannot_be_read
- まとめて承認するとき、前に並ぶ spec の予算を足して SSO を測る: plugins/spec-autopilot/tests/test_lineup.py::test_queue_measures_the_sso_session_with_the_budgets_queued_before
- 見回り役の plist の有無の判定: plugins/spec-autopilot/tests/test_watch.py::test_preflight_notes_a_missing_watcher

## 前提
- 目的に届く: S の既定（予算 30 分・マージ後の予算なし）は合計 60 分になり NOTE が消える。M の既定（90 分）以上は今のまま出る。予算を 60 分より長く書いた昼の run には今のまま出る
- 運用: 利用者は何もしない。夜通し回す run では今と同じ NOTE が出る
- 普通のやり方: なし（この plugin 固有の検査で、比べる普通のやり方が無い）
- 過去: preflight.py の変更は GDD の lock の判定だけで、夜の NOTE の出し分けを扱った PR は無い（git log と gh pr list で確かめた）
- 前提: check は keep-awake・バッテリー・自動更新・見回り役の NOTE を、予算によらず必ず足す
  - path: plugins/spec-autopilot/scripts/preflight.py:43
- 前提: マージ後の予算を書かない spec では、マージ後の予算は予算と同じ値として読まれる
  - path: plugins/spec-autopilot/scripts/overnight.py:87-94（budgets）
- 前提: check の now は今の時刻に前に並ぶ spec の予算を足した時刻で呼ばれる
  - path: plugins/spec-autopilot/scripts/autopilot.py:619
- 前提: 空の repo で init した spec の lint は、予算が無くても macOS の自動更新と見回り役の NOTE を出す
  - コマンド: `python3 plugins/spec-autopilot/scripts/autopilot.py lint docs/specs/2026-11-26-falling-puzzle` → NOTE: macOS の更新の自動インストールが有効、NOTE: 見回り役が入っていない
  - メモ: この spec は repo の外の空の repo で init した

## 作り方
check が、予算とマージ後の予算と前に並ぶ分（now と今の時刻の差）を足した見込みの長さを求め、60 分を超えるときだけ夜の 4 つの NOTE を足す。予算が読めない spec は、長さが分からないので今と同じく NOTE を出す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | pmset・defaults の偽物を PATH に置き、予算 30 分の spec で `CLI lint` と `CLI approve` を実行する。まとめて承認で、予算 10 分の spec の後に予算 20 分の spec を並べる（マージ後の予算なしで 20＋40＝60 分） | 4 つの NOTE の語が出力に無い |
| R2 | 手元で実物 | 同じ偽物で、予算 90 分の spec と、予算 30 分・マージ後の予算 40 分の spec と、予算の無い spec と、まとめて承認で予算 20 分の spec の後に並べた予算 20 分の spec（40＋40＝80 分）で実行する | 当たる NOTE の語が出力にある |
| R3 | 手元で実物 | 予算 30 分の spec で、SSO が切れる profile と、有効な GDD の lock を置いて実行する | 今と同じ ERROR が出る |

## 制約
- 予算: 30 分
- 大きさ: S
- playbook: feature

## モデル

## 自走の範囲
- 範囲: PR まで
- QA の環境: 手元
- QA の書き込み先: なし
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: なし
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
