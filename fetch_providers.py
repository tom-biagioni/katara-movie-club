#!/usr/bin/env python3
"""Refresh providers.json — US streaming availability for every title in titles.json.

Data source: TMDB watch-providers API (licensed from JustWatch).
Requires env TMDB_API_KEY (v3 hex key or v4 read token). Stdlib only.
Run:  TMDB_API_KEY=... python3 fetch_providers.py
"""
import json, os, sys, time, subprocess
import urllib.request, urllib.parse
from datetime import date

KEY = os.environ.get("TMDB_API_KEY", "").strip()
if not KEY:
    sys.exit("TMDB_API_KEY not set")
V4 = KEY.startswith("eyJ")
BASE = "https://api.themoviedb.org/3"

def get(path, **params):
    if not V4:
        params["api_key"] = KEY
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/json"}
    if V4:
        headers["Authorization"] = f"Bearer {KEY}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception:
            # fall back to curl (helps on macOS python builds with cert issues)
            try:
                args = ["curl", "-s", "-m", "20"]
                for k, v in headers.items():
                    args += ["-H", f"{k}: {v}"]
                out = subprocess.run(args + [url], capture_output=True, text=True, timeout=25).stdout
                if out.strip():
                    return json.loads(out)
            except Exception:
                pass
        time.sleep(1 + attempt * 2)
    return None

def find_id(title, year, tv):
    kind = "tv" if tv else "movie"
    yparam = {"first_air_date_year": year} if tv else {"primary_release_year": year}
    for params in ({"query": title, **yparam}, {"query": title}):
        j = get(f"/search/{kind}", **params)
        results = (j or {}).get("results") or []
        if results:
            return results[0]["id"], kind
    return None, kind

# add-on rebundles and live-TV bundles are noise for "which service is it on?"
DROP = ("Channel", "YouTube TV", "fuboTV", "Philo", "Sling", "DIRECTV", "Spectrum", "Xfinity")
STRIP = (" Standard with Ads", " with Ads", " With Ads", " (via Prime Video)")
PREFIX_MAP = (  # collapse tier variants to one family name
    ("Peacock", "Peacock"),
    ("Paramount Plus", "Paramount+"),
    ("Paramount+", "Paramount+"),
    ("Amazon Prime Video", "Prime Video"),
    ("Apple TV", "Apple TV+"),
    ("Hulu", "Hulu"),
    ("Netflix", "Netflix"),
    ("Disney Plus", "Disney+"),
)

def clean(names):
    seen, out = set(), []
    for n in names:
        if any(d in n for d in DROP):
            continue
        for s in STRIP:
            n = n.replace(s, "")
        n = n.strip()
        for prefix, family in PREFIX_MAP:
            if n.startswith(prefix):
                n = family
                break
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out[:4]

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    import re as _re
    titles = []
    with open(os.path.join(root, "data", "movies.jsonl")) as fh:
        for line in fh:
            if line.strip():
                m = json.loads(line)
                titles.append({"id": _re.sub(r"[^a-z0-9]", "", m["t"].lower()) + str(m["y"]),
                               "t": m["t"], "y": m["y"], "tv": bool(m.get("tv"))})
    us, misses = {}, []
    for i, t in enumerate(titles):
        tid, kind = find_id(t["t"], t["y"], t["tv"])
        if not tid:
            misses.append(t["t"])
            continue
        j = get(f"/{kind}/{tid}/watch/providers") or {}
        region = (j.get("results") or {}).get("US") or {}
        names = [p["provider_name"] for grp in ("flatrate", "free", "ads")
                 for p in region.get(grp, [])]
        entry = {"s": clean(names)}
        if region.get("link"):
            entry["l"] = region["link"]
        us[t["id"]] = entry
        time.sleep(0.15)
        if i % 40 == 39:
            print(f"  ...{i+1}/{len(titles)}", flush=True)
    out = {"generated": date.today().isoformat(), "us": us}
    json.dump(out, open(os.path.join(root, "providers.json"), "w"), ensure_ascii=False)
    streaming = sum(1 for e in us.values() if e["s"])
    print(f"{len(us)}/{len(titles)} titles resolved, {streaming} on a subscription service, {len(misses)} misses: {misses}")

if __name__ == "__main__":
    main()
