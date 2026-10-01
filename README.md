# stock-influencer-bot

株インフルエンサーのXアカウントを GitHub Actions で定時チェックし、新着ツイート(RT除く)を Discord に通知する。
TwitterAPI.io の `/twitter/user/last_tweets` を使用。

- 実行: JST 08:00 / 11:00 / 13:00 / 15:30 / 22:00(GitHub側で数分遅れることがある)
- 監視アカウント: `config.json`
- 既読管理: `state.json`(アカウントごとの最新ツイートID。実行後に自動コミット)
- 初回実行は既読登録のみで通知しない

## セットアップ
リポジトリの Settings → Secrets and variables → Actions に登録:

- `TWITTER_API_KEY`
- `DISCORD_WEBHOOK_URL`

Actions タブの `notify` → Run workflow で手動実行できる(初回は既読登録のみ)。
