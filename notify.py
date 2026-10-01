import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "state.json"

API_URL = "https://api.twitterapi.io/twitter/user/last_tweets"


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def get_tweets(api_key, username):
    """最新ツイートを返す。取得失敗時は None(空と区別する)。"""
    try:
        res = requests.get(
            API_URL,
            headers={"x-api-key": api_key},
            params={"userName": username},
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"[ERROR] {username}: {e}")
        return None
    if res.status_code != 200:
        print(f"[ERROR] {username}: HTTP {res.status_code}")
        return None
    return res.json().get("data", {}).get("tweets", [])


def is_retweet(t):
    return bool(t.get("isRetweet")) or t.get("text", "").startswith("RT @")


def send_discord(webhook, username, name, text, url):
    payload = {
        "embeds": [
            {
                "author": {"name": f"@{username} ({name})", "url": f"https://x.com/{username}"},
                "description": text,
                "color": 0x1DA1F2,
                "fields": [{"name": "Link", "value": url}],
                "footer": {"text": "Stock Bot"},
            }
        ]
    }
    for _ in range(2):
        try:
            res = requests.post(webhook, json=payload, timeout=15)
        except requests.RequestException as e:
            print(f"[Discord] Error: {e}")
            return False
        if res.status_code in (200, 204):
            return True
        if res.status_code == 429:
            time.sleep(float(res.json().get("retry_after", 2)) + 0.5)
            continue
        print(f"[Discord] NG {res.status_code}")
        return False
    return False


def main():
    api_key = os.environ.get("TWITTER_API_KEY")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not api_key or not webhook:
        print("TWITTER_API_KEY / DISCORD_WEBHOOK_URL が未設定です")
        sys.exit(1)

    accounts = load_json(CONFIG_PATH, {}).get("accounts", [])
    state = load_json(STATE_PATH, {})  # {username: 最新の既読ツイートID(int)}
    failed = False

    for i, username in enumerate(accounts):
        if i:
            time.sleep(3)
        tweets = get_tweets(api_key, username)
        if tweets is None:
            failed = True
            continue
        tweets = [t for t in tweets if str(t.get("id", "")).isdigit()]
        if not tweets:
            print(f"[CHECK] @{username}: 0 tweets")
            continue

        # 初回は既読登録のみ(通知しない)
        if username not in state:
            state[username] = max(int(t["id"]) for t in tweets)
            print(f"[INIT] @{username}: last_id={state[username]}")
            continue

        last_id = state[username]
        new = sorted((t for t in tweets if int(t["id"]) > last_id), key=lambda t: int(t["id"]))
        sent = 0
        for t in new:
            tid = int(t["id"])
            if not is_retweet(t):
                name = t.get("author", {}).get("name", username)
                url = f"https://x.com/{username}/status/{tid}"
                if not send_discord(webhook, username, name, t.get("text", ""), url):
                    failed = True
                    break  # 失敗分は既読にせず次回再送
                sent += 1
                time.sleep(1)
            last_id = tid
        state[username] = last_id
        print(f"[CHECK] @{username}: {sent} new tweets")

    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
