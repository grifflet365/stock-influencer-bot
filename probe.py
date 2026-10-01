"""advanced_searchの時間絞り込みがどの書き方で効くかを調べる(手動実行専用)。

効いていれば直近のツイートがなく0件(15クレジット)、効いていなければ20件(300クレジット)になる。
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from notify import SEARCH_URL, tweet_time

BASE = Path(__file__).parent
JST = timezone(timedelta(hours=9))


def run(api_key, label, query):
    res = requests.get(
        SEARCH_URL,
        headers={"x-api-key": api_key},
        params={"query": query, "queryType": "Latest", "cursor": ""},
        timeout=30,
    )
    if res.status_code != 200:
        print(f"[{label}] HTTP {res.status_code}")
        return
    body = res.json()
    body = body.get("data", body) if "tweets" not in body else body
    ids = [int(t["id"]) for t in body.get("tweets", []) if str(t.get("id", "")).isdigit()]
    if ids:
        fmt = lambda i: datetime.fromtimestamp(tweet_time({"id": i}), JST).strftime("%m/%d %H:%M")
        span = f"{fmt(min(ids))} 〜 {fmt(max(ids))}"
    else:
        span = "-"
    print(f"[{label}] query={query!r} count={len(ids)} span={span}")


def main():
    api_key = os.environ["TWITTER_API_KEY"]
    accounts = json.loads((BASE / "config.json").read_text(encoding="utf-8"))["accounts"]
    state = json.loads((BASE / "state.json").read_text(encoding="utf-8"))
    a, b = accounts[0], accounts[1]
    now = int(time.time())
    newest_seen = max(state.get("seen_ids", [0]))

    variants = [
        ("1 since_time", f"from:{a} since_time:{now - 600}"),
        ("2 括弧+OR", f"(from:{a} OR from:{b}) since_time:{now - 600}"),
        ("3 within_time", f"from:{a} within_time:1h"),
        ("4 since_id", f"from:{a} since_id:{newest_seen}"),
    ]
    for label, query in variants:
        run(api_key, label, query)
        time.sleep(2)


if __name__ == "__main__":
    main()
