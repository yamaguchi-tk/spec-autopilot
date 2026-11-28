# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: consent.py に承認の中身のハッシュと記録・起点の関数を置き、`autopilot.py lint` の CLI が通ったときだけ state.json に記録し、approve（人の発言の門）の起点にする [R1, R2]
  - メモ: 起点は min(記録の時刻, spec.md の最後の変更) にした（人の発言の後に初めて lint しても、中身が同じなら今までどおり通る）。記録は discovery・blocked・done のときだけ書く。実装役はテストを実装の後に書いた（実装を壊して落ちることは確かめた）
- [x] T2: `--by-advisor` の承認し直しと目的の spec の子の承認（goal.py の child_errors）の起点を T1 と同じにし、advisor_approval.py の文・commands/autopilot.md の起点の説明・test_goal_child.py の文を合わせる [R3]
- [x] T3: 評価役の low 2 件を直す。lint のたびに spec のディレクトリに `.state.json.lock` が残らないようにする（ファイルを作らずに、spec のディレクトリの fd に flock を取るなど）。record の docstring を、守るのは lint 同士の書き込みだけだと直す [R1]
- [x] T4: 評価役の high（R2）を直す。lint(A) → lint せずに B に直す → 人の発言 → A に戻す、で approve が通る。記録に lint の時点の spec.md の mtime と、連番を含む本文全体のハッシュも残し、今の spec.md の mtime が記録の mtime と違うときは、本文全体が lint の時点から連番の桁だけ違う（本文全体のハッシュは違い、連番を外したハッシュは同じ）ときに限って記録の時刻を起点にし、それ以外（本文全体が lint の時点と同じまま mtime だけ変わったときを含む）は spec.md の最後の変更を起点にする。.autopilot-qa/check.py の R2 と docs/specs/2026-11-28-lint-origin/inputs/R2.md の場合をテストにする [R2]
  - メモ: A → B → 連番を変えた A' の順は履歴が無く見分けられない（評価役も直し方の案で同じと書いた）。ADR の Consequences に限界として書き、朝の報告に出す
- [x] T5: commands/autopilot.md の B の 3・4 に、spec を人に示す前と、照合役の ng や人の直しの指示で直して示し直す前に、毎回 `CLI lint` を通すと書き、B の 5 の承認の返事の項と揃える。lint(B) を通してから示した中身の連番だけの直しは通り、連番ごと lint(A) の中身へ戻すと断ることをテストにする [R2, R4]
- [x] T6: 評価役の low を直す。spec のディレクトリに書き込めないとき、lint が `lint: OK` の後に consent.record の tmp の書き込み（write_text・os.replace）で PermissionError の traceback を出して exit 1 になる。record で書き込みの OSError を捕まえ、state.json が読めないときと同じく NOTE を返し、tmp が残らないようにする（lint の終了コードは変えない）。書き込めないディレクトリで lint が NOTE と exit 0 になることをテストにする [R1]
  - メモ: 3 巡目の評価役の low（spec のディレクトリに読み取り権が無いと consent.record の os.open が try の外で traceback になる）は直さない。通常は起きない権限で、記録は残らず承認は mtime の起点に倒れる（緩む方に行かない）。予算の残りが 22 分で直しの巡が収まらないので、朝の報告に出して別に直す
