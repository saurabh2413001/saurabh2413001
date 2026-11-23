#!/usr/bin/env python3
"""Fetch coding ratings and update the table inside README.md.

If any platform fails, the last known value (ratings.json) is kept,
so the README never breaks.
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CACHE = ROOT / "ratings.json"

USERS = {
    "leetcode": "saurabh_bhati",
    "codeforces": "Saurabh2413001",
    "codechef": "quick_web_79",
    "atcoder": "thakur_saurabh",
}

# Used only on the very first run / if a fetch fails before any cache exists
DEFAULTS = {
    "leetcode": {"rating": 1674, "peak": 1725},
    "codechef": {"rating": 1557},
    "codechef_dsa": {"rating": 2087},  # no public API -> stays static
    "codeforces": {"rating": 1356},
    "atcoder": {"rating": 1375},
}

HEADERS = {"User-Agent": "Mozilla/5.0 (rating-updater)"}


def http(url, data=None, headers=None):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_leetcode(user):
    query = """
    query($u:String!){
      userContestRanking(username:$u){rating}
      userContestRankingHistory(username:$u){attended rating}
    }"""
    body = json.dumps({"query": query, "variables": {"u": user}}).encode()
    raw = http(
        "https://leetcode.com/graphql",
        data=body,
        headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
    )
    d = json.loads(raw)["data"]
    rating = round(d["userContestRanking"]["rating"])
    hist = [h["rating"] for h in d["userContestRankingHistory"] if h["attended"]]
    peak = round(max(hist + [rating]))
    return {"rating": rating, "peak": peak}


def fetch_codeforces(user):
    d = json.loads(http(f"https://codeforces.com/api/user.info?handles={user}"))
    u = d["result"][0]
    return {"rating": u["rating"]}


def fetch_atcoder(user):
    hist = json.loads(http(f"https://atcoder.jp/users/{user}/history/json"))
    rated = [h for h in hist if h.get("IsRated")]
    return {"rating": rated[-1]["NewRating"]}


def fetch_codechef(user):
    html = http(f"https://www.codechef.com/users/{user}")
    m = re.search(r'class="rating-number"[^>]*>\s*(\d+)', html)
    if not m:
        raise ValueError("CodeChef rating not found")
    return {"rating": int(m.group(1))}


FETCHERS = {
    "leetcode": fetch_leetcode,
    "codeforces": fetch_codeforces,
    "atcoder": fetch_atcoder,
    "codechef": fetch_codechef,
}


def main():
    data = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)

    for name, fn in FETCHERS.items():
        try:
            data[name] = fn(USERS[name])
            print(f"[ok]   {name}: {data[name]}")
        except Exception as e:  # keep old value on failure
            print(f"[fail] {name}: {e} (keeping {data[name]})")

    CACHE.write_text(json.dumps(data, indent=2))

    table = (
        "| Platform | Rating |\n"
        "|:---:|:---:|\n"
        f"| 🟠 [LeetCode](https://leetcode.com/u/{USERS['leetcode']}) | "
        f"**{data['leetcode']['rating']}** (Peak: {data['leetcode']['peak']}) |\n"
        f"| 🟡 [CodeChef](https://www.codechef.com/users/{USERS['codechef']}) | "
        f"**{data['codechef']['rating']}** |\n"
        f"| 🟡 CodeChef DSA | **{data['codechef_dsa']['rating']}** |\n"
        f"| 🔵 [Codeforces](https://codeforces.com/profile/{USERS['codeforces']}) | "
        f"**{data['codeforces']['rating']}** |\n"
        f"| 🟣 [AtCoder](https://atcoder.jp/users/{USERS['atcoder']}) | "
        f"**{data['atcoder']['rating']}** |"
    )

    text = README.read_text(encoding="utf-8")
    new = re.sub(
        r"(<!--RATINGS_START-->\n).*?(\n<!--RATINGS_END-->)",
        lambda m: m.group(1) + table + m.group(2),
        text,
        flags=re.S,
    )
    README.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
