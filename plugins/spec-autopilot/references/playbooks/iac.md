# playbook: iac（Terraform などで環境を作る・変える）

選ぶとき: Terraform などで AWS・GCP の資源を作る・変える・消す spec。権限を絞る変更もここ。

## spec を書くとき（A・B）

- QA の方向性に、対象のアカウントでの plan（`terraform plan -lock=false`。state を書かない）を確かめ方に書く。作業ディレクトリ・backend の設定・`-var-file` か workspace・認証の profile か role と、対象のアカウント ID を書く
- 合格基準は「エラーが無く、作る <n>・変える <n>・消す <n>（消す・置き換えは 0 か、列挙したものだけ）」の形で数を書く。`terraform validate`・`fmt` だけを証拠にしない（plan も apply も回さずに done にした spec が、新しいアカウントの初回の apply で落ちる指摘を 10 件受けた）
- plan を回す認証が手元に無いなら、合意の前に人に聞く。人が、plan を CI で回す・対象のアカウントがまだ無いなどと答えたときだけ、合格基準に `unverified（<人の答えの要約。CI の workflow のパスか、対象のアカウントが無い理由>）` と書き、QA の方向性に `- unverified の承認: R<n>（同じ理由）` を書く（人に聞かずに書かない。承認のときは先頭に示す）
- マージで CI が apply する repo（tfaction など）では、`- デプロイの起動: マージで自動`、`- デプロイの確かめ:` にその apply の workflow を書く。agent は apply を打たない（`commands/autopilot.md` の C の安全規則）
- 権限の案は、最小の権限だけでなく運用の手間（人が毎回付け外しするか、ロールの切り替えで済むか）で比べ、推奨を選ぶ（運用の手間から権限の案を出し直させた事例が 3 件ある）
- 使う資源・引数が入った provider の版を、provider の CHANGELOG で調べ、repo が固定する版（`.terraform.lock.hcl` など）と比べる。結果は「## 前提」に確認日と出典の URL の行つきで残す（URL の行には URL だけを書き、後ろに文字を書かない）。固定の版が古ければ、版を上げることも要件に含めるかを書く。利用者の手元に最新を調べる skill があれば、それに従ってよい

  ```
  - 前提: <資源>の <引数>は provider <版> で入り、repo の固定は <版>（確認日 2026-11-26）
    - URL: https://github.com/hashicorp/terraform-provider-aws/blob/main/CHANGELOG.md
  ```

- 道具の版は repo の aqua などで固定したものを前提にする（手元に入っている版を前提にしない）
- `- AWS の profile:` と plan の認証を、対象のアカウントのものにする。前提に `aws sts get-caller-identity` の結果を書く

## 自走のタスク（A の 0 で選んだらすぐ tasks.md の先頭に写す）

- 種類に固有のタスクは無い。plan は評価役が QA の方向性のとおりに回す

## 評価役の観点

- 初回の apply と権限（plan が通っても初回の apply で落ちる型は、評価役の定義の 9 の表が、playbook の選びによらず差分の IaC に当てる）
