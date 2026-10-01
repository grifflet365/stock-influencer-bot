# stock-influencer-bot

株インフルエンサーのXアカウントを GitHub Actions で定時チェックし、新着ツイート(RT除く)を Discord に通知する。
TwitterAPI.io の `tweet/advanced_search` で全アカウントを1回の呼び出しでまとめて検索し、前回以降の新着だけ取得する(クレジット節約)。

- 実行(JST): 08:30〜15:30は30分おき、17:30/19:30/21:30/23:30、00:30、04:30(GitHub側で数分遅れることがある)
- 監視アカウント: `config.json`
- 既読管理: `state.json`(前回チェック時刻と既読ID。実行後に自動コミット)
- 初回実行は既読登録のみで通知しない

## セットアップ
リポジトリの Settings → Secrets and variables → Actions に登録:

- `TWITTER_API_KEY`
- `DISCORD_WEBHOOK_URL`

Actions タブの `notify` → Run workflow で手動実行できる(初回は既読登録のみ)。
