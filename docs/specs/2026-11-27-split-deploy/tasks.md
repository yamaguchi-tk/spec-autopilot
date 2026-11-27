# タスク

- [ ] T1: overnight.py:50-510（範囲・デプロイ・本番・ロールバック）と 652-752（待ちの記録と予算）を scripts/deploy.py にそのまま移し、overnight.py・autopilot.py・lineup.py・light.py・preflight.py・watch.py・hooks/stop.py・テストの参照を deploy へ向け直す [R1]
  - メモ: 移す名前は spec の影響範囲の 2 行の一覧が正本。R1 の CLI の列挙は例示なので、向け直しは移した名前ごとの grep で拾う（rolled-back の rollback_cmd・deploy_floor、park の PARK_KINDS も入る）
  - メモ: `import overnight` の形だけでなく、autopilot.py:1058・1079 の `__import__("overnight")` の形も deploy へ向ける
  - メモ: hooks/stop.py の awaiting（94）と judge_building、watch.py の awaiting（142）・tick_one（250）は、モジュールを引数 `overnight` で受け取って await_record を呼ぶ。渡すモジュールを deploy にし、引数の名前も deploy に変える（名前の頭を変えるだけ）
  - メモ: preflight.py:53・132 のコメントの `overnight.budgets`・`overnight.scope_rows` も deploy に直す
  - メモ: overnight.py は冒頭で `from deploy import ...` と、自分の中で使う名前だけを取り込む。外へ出し直す import はしない。stop.py の import は今の overnight の import と同じく関数の中に置く
