#!/usr/bin/env python3
"""Add a title to the collection via TMDB lookup.

  TMDB_API_KEY=... python3 pipeline/add_title.py --query "Heat" --year 1995 \
      --type movie [--notes "..."] [--moods crime,tense] [--spook 2] [--dry-run]

Appends to data/movies.jsonl, saves posters/<slug>.jpg, patches providers.json.
Refuses duplicates. Stdlib only. Exit codes: 0 ok, 2 duplicate, 3 not found.
"""
import argparse, json, os, re, sys, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("TMDB_API_KEY", "").strip()
if not KEY:
    sys.exit("TMDB_API_KEY not set")
V4 = KEY.startswith("eyJ")

def get(path, **params):
    if not V4:
        params["api_key"] = KEY
    url = f"https://api.themoviedb.org/3{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=(
        {"Authorization": f"Bearer {KEY}", "Accept": "application/json"} if V4
        else {"Accept": "application/json"}))
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())
def slugify(t, y): return norm(t) + str(y)

GENRE_MAP = {
    "Action": "Action", "Adventure": "Adventure", "Animation": "Animation",
    "Comedy": "Comedy", "Crime": "Crime", "Documentary": "Documentary",
    "Drama": "Drama", "Fantasy": "Fantasy", "History": "Drama",
    "Horror": "Horror", "Music": "Music", "Mystery": "Mystery",
    "Romance": "Romance", "Science Fiction": "Sci-Fi", "Thriller": "Thriller",
    "War": "War", "Western": "Western", "Sci-Fi & Fantasy": "Sci-Fi",
    "Action & Adventure": "Action", "War & Politics": "War",
}
MOOD_FROM_GENRE = [
    ("Comedy", "funny"), ("Horror", "scary"), ("Thriller", "tense"),
    ("Crime", "crime"), ("Action", "action"), ("Mystery", "mindbendy"),
    ("Adventure", "epic"), ("War", "epic"), ("Western", "epic"),
    ("Drama", "feels"), ("Romance", "feels"), ("Animation", "feelgood"),
]
DROP = ("Channel", "YouTube TV", "fuboTV", "Philo", "Sling", "DIRECTV", "Spectrum", "Xfinity")
STRIP = (" Standard with Ads", " with Ads", " With Ads", " (via Prime Video)")
PREFIX_MAP = (("Peacock", "Peacock"), ("Paramount Plus", "Paramount+"), ("Paramount+", "Paramount+"),
              ("Amazon Prime Video", "Prime Video"), ("Apple TV", "Apple TV+"),
              ("Hulu", "Hulu"), ("Netflix", "Netflix"), ("Disney Plus", "Disney+"))

def clean_providers(names):
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
            seen.add(n); out.append(n)
    return out[:4]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--type", choices=["movie", "tv"], default="movie")
    ap.add_argument("--notes", default="")
    ap.add_argument("--moods", default="")
    ap.add_argument("--spook", type=int, default=-1)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    # pull a trailing year out of the query if present
    q, year = a.query.strip(), a.year
    ym = re.search(r"\(?(19|20)\d\d\)?\s*$", q)
    if ym and not year:
        year = int(re.sub(r"[^\d]", "", ym.group(0)))
        q = q[:ym.start()].strip()

    tv = a.type == "tv"
    kind = "tv" if tv else "movie"
    yparam = ({"first_air_date_year": year} if tv else {"primary_release_year": year}) if year else {}
    results = get(f"/search/{kind}", query=q, **yparam).get("results") or []
    if not results and year:
        results = get(f"/search/{kind}", query=q).get("results") or []
    if not results:
        print(f"NOT FOUND on TMDB: {q!r}")
        sys.exit(3)
    hit = results[0]
    tid = hit["id"]
    title = hit.get("name") if tv else hit.get("title")
    date = (hit.get("first_air_date") if tv else hit.get("release_date")) or "0000"
    y = int(date[:4]) if date[:4].isdigit() else year

    # duplicate check against the catalog
    existing = []
    with open(os.path.join(ROOT, "data", "movies.jsonl")) as fh:
        for line in fh:
            if line.strip():
                existing.append(json.loads(line))
    new_slug = slugify(title, y)
    for m in existing:
        if slugify(m["t"], m["y"]) == new_slug or (norm(m["t"]) == norm(title) and abs(m["y"] - y) <= 1):
            print(f"DUPLICATE: already in the collection as {m['t']} ({m['y']})")
            sys.exit(2)

    det = get(f"/{kind}/{tid}", append_to_response="credits,release_dates" if not tv else "content_ratings")

    if tv:
        creators = [c["name"] for c in det.get("created_by") or []]
        director = " & ".join(creators[:2]) if creators else "Unknown"
    else:
        crew = (det.get("credits") or {}).get("crew") or []
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        director = " & ".join(directors[:2]) if directors else "Unknown"

    rating = ""
    if tv:
        for r in ((det.get("content_ratings") or {}).get("results") or []):
            if r.get("iso_3166_1") == "US" and r.get("rating"):
                rating = r["rating"]; break
        rating = rating or "TV-MA"
    else:
        for r in ((det.get("release_dates") or {}).get("results") or []):
            if r.get("iso_3166_1") == "US":
                for rd in r.get("release_dates") or []:
                    if rd.get("certification"):
                        rating = rd["certification"]; break
            if rating: break
        rating = rating or "NR"

    genres = []
    for g in det.get("genres") or []:
        mapped = GENRE_MAP.get(g["name"])
        if mapped and mapped not in genres:
            genres.append(mapped)
    genres = genres[:3] or (["Drama"] if not tv else ["Drama"])

    if a.moods:
        moods = [m.strip() for m in a.moods.split(",") if m.strip()][:3]
    else:
        moods = []
        for g, mood in MOOD_FROM_GENRE:
            if g in genres and mood not in moods:
                moods.append(mood)
        moods = moods[:3] or ["feels"]

    spook = a.spook if a.spook >= 0 else (2 if "Horror" in genres else 0)
    entry = {"t": title, "y": y, "d": director, "r": rating, "tm": tid}
    if tv:
        last = (det.get("last_air_date") or "")[:4]
        in_prod = det.get("in_production")
        entry.update({"tv": True, "sea": det.get("number_of_seasons") or 1,
                      "net": ((det.get("networks") or [{}])[0].get("name") or "—"),
                      "yrs": f"{y}-" if in_prod else (f"{y}-{last}" if last and last != str(y) else str(y))})
    else:
        entry["rt"] = det.get("runtime") or 0
    entry["g"] = genres
    entry["m"] = moods
    if spook: entry["sp"] = spook
    if (det.get("original_language") or "en") != "en": entry["sub"] = True
    entry["p"] = a.notes.strip() or "Program notes pending. The management will get to it."

    # streaming availability for the new title
    prov_entry = None
    try:
        region = (get(f"/{kind}/{tid}/watch/providers").get("results") or {}).get("US") or {}
        names = [p["provider_name"] for grp in ("flatrate", "free", "ads") for p in region.get(grp, [])]
        prov_entry = {"s": clean_providers(names)}
        if region.get("link"): prov_entry["l"] = region["link"]
    except Exception:
        pass

    poster_url = None
    if hit.get("poster_path"):
        poster_url = "https://image.tmdb.org/t/p/w342" + hit["poster_path"]

    print(json.dumps({"resolved": f"{title} ({y})", "tmdb": tid, "director": director,
                      "rating": rating, "genres": genres, "moods": moods, "spook": spook,
                      "streaming": (prov_entry or {}).get("s"), "poster": bool(poster_url),
                      "slug": new_slug}, indent=2))
    if a.dry_run:
        print("DRY RUN — nothing written.")
        return

    if poster_url:
        req = urllib.request.Request(poster_url, headers={"User-Agent": "KataraMovieClub/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) > 2000:
            open(os.path.join(ROOT, "posters", new_slug + ".jpg"), "wb").write(data)

    with open(os.path.join(ROOT, "data", "movies.jsonl"), "a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    ppath = os.path.join(ROOT, "providers.json")
    if prov_entry is not None and os.path.exists(ppath):
        prov = json.load(open(ppath))
        prov.setdefault("us", {})[new_slug] = prov_entry
        json.dump(prov, open(ppath, "w"), ensure_ascii=False)

    print(f"ADDED: {title} ({y}) as entry #{len(existing)+1}")

if __name__ == "__main__":
    main()
