# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: consent.py に承認の中身のハッシュと記録・起点の関数を置き、`autopilot.py lint` の CLI が通ったときだけ state.json に記録し、approve（人の発言の門）の起点にする [R1, R2]
  - メモ: 起点は min(記録の時刻, spec.md の最後の変更) にした（人の発言の後に初めて lint しても、中身が同じなら今までどおり通る）。記録は discovery・blocked・done のときだけ書く。実装役はテストを実装の後に書いた（実装を壊して落ちることは確かめた）
- [x] T2: `--by-advisor` の承認し直しと目的の spec の子の承認（goal.py の child_errors）の起点を T1 と同じにし、advisor_approval.py の文・commands/autopilot.md の起点の説明・test_goal_child.py の文を合わせる [R3]
- [x] T3: 評価役の low 2 件を直す。lint のたびに spec のディレクトリに `.state.json.lock` が残らないようにする（ファイルを作らずに、spec のディレクトリの fd に flock を取るなど）。record の docstring を、守るのは lint 同士の書き込みだけだと直す [R1]
- [x] T4: 評価役の high（R2）を直す。lint(A) → lint せずに B に直す → 人の発言 → A に戻す、で approve が通る。記録に lint の時点の spec.md の mtime と、連番を含む本文全体のハッシュも残し、今の spec.md の mtime が記録の mtime と違うときは、本文全体が lint の時点から連番の桁だけ違う（本文全体のハッシュは違い、連番を外したハッシュは同じ）ときに限って記録の時刻を起点にし、それ以外（本文全体が lint の時点と同じまま mtime だけ変わったときを含む）は spec.md の最後の変更を起点にする。.autopilot-qa/check.py の R2 と docs/specs/2026-11-28-lint-origin/inputs/R2.md の場合をテストにする [R2]
  - メモ: A → B → 連番を変えた A' の順は履歴が無く見分けられない（評価役も直し方の案で同じと書いた）。ADR の Consequences に限界として書き、朝の報告に出す
