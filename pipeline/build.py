#!/usr/bin/env python3
"""Build the site into dist/ from data/movies.jsonl + posters/ + pipeline/template.html.

Run from anywhere: python3 pipeline/build.py
Outputs: dist/index.html, dist/titles.json, plus copies of providers.json,
add.html, and apple-touch-icon.png. Also build/artifact.html (unwrapped variant).
"""
import json, base64, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPE = os.path.join(ROOT, "pipeline")
DIST = os.path.join(ROOT, "dist")
os.makedirs(DIST, exist_ok=True)

def slug(m): return re.sub(r"[^a-z0-9]", "", m["t"].lower()) + str(m["y"])

movies = []
with open(os.path.join(ROOT, "data", "movies.jsonl")) as fh:
    for line in fh:
        if line.strip():
            movies.append(json.loads(line))

posters = {}
total = 0
for m in movies:
    s = slug(m)
    p = os.path.join(ROOT, "posters", s + ".jpg")
    if os.path.exists(p) and os.path.getsize(p) > 2000:
        b = open(p, "rb").read()
        total += len(b)
        posters[s] = "data:image/jpeg;base64," + base64.b64encode(b).decode()

font = ""
fp = os.path.join(PIPE, "limelight-latin.woff2")
if os.path.exists(fp):
    font = "data:font/woff2;base64," + base64.b64encode(open(fp, "rb").read()).decode()

html = open(os.path.join(PIPE, "template.html")).read()
html = html.replace("__FONT__", font)
html = html.replace("__DATA__", json.dumps(movies, ensure_ascii=False))
html = html.replace("__POSTERS__", json.dumps(posters))

favicon_svg = ""
ip = os.path.join(PIPE, "icon.svg")
if os.path.exists(ip):
    favicon_svg = "data:image/svg+xml;base64," + base64.b64encode(open(ip, "rb").read()).decode()

head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Katara's Movie Club</title>
<meta name="description" content="The collection: films and shows selected by the management (Dad).">
<meta name="theme-color" content="#111114">
<link rel="icon" href="{favicon_svg}">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Movie Club">
<meta property="og:title" content="Katara's Movie Club">
<meta property="og:description" content="The collection: films and shows selected by the management (Dad).">
</head>
<body>
"""
body = html
for tag in ('<meta charset="utf-8">', "<title>Katara's Movie Club</title>",
            '<meta name="viewport" content="width=device-width, initial-scale=1">'):
    body = body.replace(tag + "\n", "", 1)

with open(os.path.join(DIST, "index.html"), "w") as fh:
    fh.write(head + body + "\n</body>\n</html>\n")

# unwrapped variant for the claude.ai artifact mirror (not deployed)
os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
with open(os.path.join(ROOT, "build", "artifact.html"), "w") as fh:
    fh.write(html)

titles = [{"id": slug(m), "t": m["t"], "y": m["y"], "tv": bool(m.get("tv"))} for m in movies]
json.dump(titles, open(os.path.join(DIST, "titles.json"), "w"), ensure_ascii=False)

for extra in ("providers.json", "add.html"):
    src = os.path.join(ROOT, extra)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(DIST, extra))
for asset in ("apple-touch-icon.png", "sw.js", "manifest.webmanifest", "icon-192.png", "icon-512.png"):
    shutil.copy(os.path.join(PIPE, asset), os.path.join(DIST, asset))

n_films = sum(1 for m in movies if not m.get("tv"))
print(f"built dist/: {len(movies)} titles ({n_films} films), {len(posters)} posters, "
      f"index {os.path.getsize(os.path.join(DIST,'index.html'))//1024}KB")
