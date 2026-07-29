# Katara's Movie Club 🎬

The collection: 224 films and 22 shows selected by the management (Dad),
served as a single-page catalog at https://tom-biagioni.github.io/katara-movie-club/

## How it's built

- `data/movies.jsonl` — one JSON line per title (metadata, moods, program notes)
- `posters/` — small poster JPEGs, baked into the page as data URIs at build time
- `pipeline/template.html` + `pipeline/build.py` — the app and its builder
- `providers.json` — US streaming availability (JustWatch data via TMDB),
  refreshed monthly by `.github/workflows/refresh-providers.yml`
- Every push to `main` rebuilds and deploys via `.github/workflows/deploy.yml`
  (GitHub Pages, workflow build — `dist/` is never committed)

## Adding a title

Three ways, easiest first:

1. **The Management's Office** — [add.html](https://tom-biagioni.github.io/katara-movie-club/add.html):
   search, press Add, submit the prefilled form. The archivist (an Action) looks the
   title up on TMDB, fetches the poster, metadata, and streaming availability,
   refuses duplicates, and deploys. Issues opened by anyone other than the
   management are labeled `petition` and wait for an `approved` label.
2. **GitHub issue** — open an "Add a title" issue directly.
3. **Locally**:
   ```
   TMDB_API_KEY=... python3 pipeline/add_title.py --query "Heat 1995" --notes "..."
   git add data posters providers.json && git commit && git push
   ```

Program notes left blank are filed as "pending" — the voice of the catalog is
the management's, not the robot's.

Original list preserved in `Mind Map 4.md`. Poster thumbnails belong to their
respective studios; this is a private family catalog.
