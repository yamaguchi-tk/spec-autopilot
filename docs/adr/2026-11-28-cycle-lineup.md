# ADR: lineup.py の名前を、autopilot.py に依らないものは下の層の after.py・building.py に、承認の道のものは autopilot.py に分けて出す

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-lineup

## Context
import の輪は autopilot・lineup・overnight の 3 つで残る。autopilot.py は lineup.py の after_name・queue_lint・enqueue・begin を呼び、lineup.py は autopilot.py の lint・take_over・sha などを呼ぶので輪になる。親の spec は、lineup を autopilot.py の上に立つ CLI の入口として扱い、autopilot.py に依らないもの（after_name・begin）は下の層に出し、承認の道で autopilot.py の lint・take_over を使うもの（queue_lint・enqueue）は、それらが呼ぶ lineup の補助ごと autopilot.py に移す（lineup.py も使う補助は下の層に置いて両方から読む）と決めた。begin は autopilot.py の sha を使うので、sha も同じ子で下の層に出す。

## 選択肢
1. 下の層を役ごとに 2 つにする: after.py（依る spec の名前と、後の spec と依る spec の対の記録）と building.py（承認の対象のハッシュと、承認した spec を自走中にする begin）。after.py は 2 つの塊で LCOM4 2、building.py は begin → sha → head_and_body の 1 つの塊で LCOM4 1。変えるコードのファイルは 4 つ（lineup・autopilot・after・building）で、呼び出し元の light.py と合わせて M に収まる
2. 下の層を 1 つにまとめる: after_name・対の記録・begin・sha が呼び合わずに並び、LCOM4 が 3 になって悪化になる
3. 下の層を 3 つにする（sha・head_and_body を begin と別の spec_hash.py にする）: 役は細かく分かれるが、変えるコードのファイルが 5 つと呼び出し元 1 つで 6 になり、L になって 1 本の子で承認できない
4. remember も autopilot.py に移す（親の作り方の例のとおり）: lineup.py は remember を使わないが、テスト（test_lineup.py:479）が lineup.remember を別のプロセスで呼ぶので、lineup.py が autopilot.py から import し直す形が要る。remember は pairs_file・pairs と同じ塊なので、after.py に置けば両方から読め、after.py の LCOM4 も 2 のまま

## Decision
1 を選び、remember は 4 を退けて after.py に置く。中身は変えずに移す。autopilot.py に移す lineup.minutes は、done の中の同じ名前の変数と紛れないよう queue_minutes にする。

- 直し方: 設計を変える
- 退けた: 要らなくする（まとめて承認・依る spec の着手・軽量フローがこれからも使う。消せない）
- 退けた: 入力の約束を変える（spec の書式や対の記録の置き場を変えても、承認が依る spec を読む依存は残る）

## Consequences
- autopilot.py は lineup.py を import しない。lineup.py は autopilot.py・after.py・building.py・overnight.py を import する入口になる
- 輪のモジュールは、overnight.py:325 が lineup.after_name を呼ぶので 3 つのまま。overnight の子で 325 を after.py に向け直すと lineup は輪から出る
- autopilot.py の fan-out は 1 上がる（親の R5 のただし書きで数えない）
