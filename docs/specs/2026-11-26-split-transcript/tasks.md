# タスク

- [ ] T1: autopilot.py:1302-1440（区画の説明のコメントと、ANOMALY_KINDS から anomaly_line まで）を scripts/transcript.py に移し、autopilot.py・hooks/stop.py・scripts/overnight.py・tests/test_stop_bounds.py の参照を transcript へ向け直す [R1]
  - メモ: 区画の前の「自走の異常」の説明のコメントも transcript.py の冒頭へ移す（残すと session_transcript の上に浮く）
  - メモ: stop.py の anomaly_notice の中で import transcript し、transcript.anomalies をモジュール属性で参照する（test_stop_bounds.py の monkeypatch が効く形）
  - メモ: autopilot.py は re・time・datetime・json を区画の外でも使うので、その import は消さない
