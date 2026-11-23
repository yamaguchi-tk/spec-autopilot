# spec-autopilot

spec-autopilot は、Claude Code の plugin です。要件を人と壁打ちで詰め、要件・作り方・QA の方向性・制約・予算を 1 つの spec で 1 回合意したら、TDD 実装 → レビュー → QA → PR 作成まで、人に聞かずに進めます（`/autopilot`）。人に戻るのは、合意した要件を満たす方法が無いときだけです。

使い方・前提と制限は [plugins/spec-autopilot/README.md](plugins/spec-autopilot/README.md) にあります。設計の判断は [docs/adr/](docs/adr/) にあります。

## 導入（Claude Code）

```text
/plugin marketplace add yamaguchi-tk/spec-autopilot
/plugin install spec-autopilot@spec-autopilot
```

## この repo の履歴

この repo は、作者の private repo から spec-autopilot だけを切り出して、1 commit で始めています。文書の中の `#NNN` は、切り出す前の private repo の PR 番号で、この repo の Issue・PR とは別のものです。

この repo 自身の開発ルールは [CLAUDE.md](CLAUDE.md) にあります。

## ライセンス

[MIT](LICENSE)
