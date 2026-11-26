# ADR: 信頼の印は、origin の無い発言の行の時刻で確かめる

## 状況
人の役を別の agent が演じる run は、Claude Code を起動する側の環境に `SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` を立て、hook が記録に `trust: true` を書く。require_user_after は、transcript のどの行にも origin が無いときだけ、この印を見る。体験会のリハーサルでは、人の役の発言に origin が無く、subagent の報告の行にだけ origin があった。そのため印を見る分岐に届かず、approve が止まった。

## 決定
human_said_at が、origin が human の行の時刻と、origin の無い発言の行（会話の要約を除く）の時刻を返す。require_user_after は、印があるとき、どちらかが spec.md の変更より後なら通す。印が無いときの判定は変えない。

## 退けた案
- 印があれば transcript を見ずに記録の時刻だけで通す: 既存のテスト（印があっても、origin の付いた知らせだけでは通さない）の決まりを外し、subagent の報告で hook が動いた時刻でも通ってしまう
- 印の有無によらず、発言の候補の行に origin の無い行があれば出どころ不明として扱う: 対話の transcript にも origin の無い行（会話の要約・ci-monitor の知らせ）があり、印の無い普通の承認が止まる
