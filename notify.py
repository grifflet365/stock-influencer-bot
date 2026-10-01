import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "state.json"

SEARCH_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
OVERLAP_SEC = 600  # 検索インデックスの反映遅れ対策。前回時刻から少し遡って検索し、IDで重複を除く
MAX_PAGES = 5
MAX_SEEN = 1000


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def tweet_time(t):
    """ツイートIDに埋め込まれた作成時刻(UNIX秒)。"""
    return ((int(t["id"]) >> 22) + 1288834974657) // 1000


def search_new(api_key, accounts, since):
    """since以降の対象アカウントのツイートを返す。失敗時は None。"""
    # 括弧が必須。ないとsince_timeが最後のfrom:にしか効かない
    query = "(" + " OR ".join(f"from:{a}" for a in accounts) + f") since_time:{since}"
    tweets, cursor = [], ""
    for _ in range(MAX_PAGES):
        try:
            res = requests.get(
                SEARCH_URL,
                headers={"x-api-key": api_key},
                params={"query": query, "queryType": "Latest", "cursor": cursor},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"[ERROR] search: {e}")
            return None
        if res.status_code != 200:
            print(f"[ERROR] search: HTTP {res.status_code}")
            return None
        body = res.json()
        body = body.get("data", body) if "tweets" not in body else body
        page = [t for t in body.get("tweets", []) if str(t.get("id", "")).isdigit()]
        fresh = [t for t in page if tweet_time(t) >= since]
        tweets += fresh
        # since_timeが効かず古いツイートが返ってきた場合は、それ以降のページを取らない(クレジット保護)
        if len(fresh) < len(page):
            break
        if not body.get("has_next_page") or not body.get("next_cursor"):
            break
        cursor = body["next_cursor"]
        time.sleep(1)
    return tweets


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
    state = load_json(STATE_PATH, {})  # {"last_checked": UNIX秒, "seen_ids": [...]}
    now = int(time.time())

    # 初回(旧形式のstate含む)は時刻を記録するだけ。APIは呼ばず、通知もしない
    if "last_checked" not in state:
        STATE_PATH.write_text(
            json.dumps({"last_checked": now, "seen_ids": []}, indent=2), encoding="utf-8"
        )
        print(f"[INIT] last_checked={now}")
        return

    tweets = search_new(api_key, accounts, state["last_checked"] - OVERLAP_SEC)
    if tweets is None:
        sys.exit(1)  # stateは更新しない(次回同じ範囲を再取得)

    seen = set(state.get("seen_ids", []))
    new = sorted(
        (t for t in tweets if str(t.get("id", "")).isdigit() and int(t["id"]) not in seen),
        key=lambda t: int(t["id"]),
    )
    sent, failed = 0, False
    for t in new:
        tid = int(t["id"])
        if not is_retweet(t):
            author = t.get("author", {})
            username = author.get("userName", "")
            url = f"https://x.com/{username}/status/{tid}"
            if not send_discord(webhook, username, author.get("name", username), t.get("text", ""), url):
                failed = True
                continue  # 失敗分は既読にせず次回再送
            sent += 1
            time.sleep(1)
        seen.add(tid)
    print(f"[CHECK] fetched={len(tweets)} new={len(new)} sent={sent}")

    state["seen_ids"] = sorted(seen)[-MAX_SEEN:]
    if not failed:
        state["last_checked"] = now
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
