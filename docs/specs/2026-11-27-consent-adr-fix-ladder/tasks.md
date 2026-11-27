# タスク

- [x] T1: rootcause.py に合意の ADR の検査を足し、lint から初回の合意のときだけ呼ぶ。テストの雛形の ADR に段の行を足す [R1, R2, R3, R4, R5, R6]
- [x] T2: adr-template.md の段の行を合意の ADR にも使う形に直す [R7]
- [x] T3: 照合役の表に、退けた理由を目的に当てる項目を足す [R8]
- [x] T4: autopilot.md の A の 1 と A の 4 を、上の段から先に案を考えて退けた理由を ADR に書く形に直す [R9]
- [x] T5: 評価役の high を直す（照合役の項目 11 の ng の条件、autopilot.py の行数）と、文書の語だけを assert するテストを外す [R1, R7, R8]
  - メモ: 2 巡目の評価役の変異 mut-R2-3 は patch の形の誤りで当たらず印だけが残った。plugins の下が HEAD と同じ（git diff --quiet HEAD -- plugins）と確かめたので block せず、その巡の結果を捨てて .autopilot-qa を消し、評価役を回し直した
- [x] T6: UTF-8 で読めない ADR で lint が Traceback で落ちないようにする [R1]
- [x] T7: 読む権限の無い ADR で lint・承認が Traceback で落ちないようにする [R1]
