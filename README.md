# Personal Website

My portfolio site, live at **[bernielaird.com](https://bernielaird.com)**. It's built with Django and deployed on Render.

## Pages

| Page | What's there |
|---|---|
| [`/`](https://bernielaird.com) | Home |
| [`/about/`](https://bernielaird.com/about/) | About me |
| [`/projects/`](https://bernielaird.com/projects/) | Projects, with links to code and live demos |
| [`/contact/`](https://bernielaird.com/contact/) | Contact |
| [`/vct/`](https://bernielaird.com/vct/) | **VCT Win Probability**: an interactive app for my [vctstats](https://github.com/bernielaird/vctstats) project |
| [`/musicelo/`](https://www.bernielaird.com/musicelo/) | **MusicElo**: rank your music with head-to-head matchups (from the [MusicElo](https://github.com/bernielaird/MusicElo) repo) |

Every page has a light/dark mode button. The site follows the visitor's system setting until they use the button, then remembers their choice.

## VCT Win Probability (`/vct/`)

An interactive front end for a model that estimates, after every kill and spike plant in pro Valorant (VCT, 2023 onward), each team's chance of winning the round. Each swing is credited to the players who caused it: **win probability added (WPA)**.

- **Matches:** every match, filterable by year, tournament and team. Each match page has the round-by-round results for every map (in team colors) and every player's stats, for the whole match and each map.
- **Round explorer:** a win-probability chart for any round, kill by kill, with each player's credit.
- **Best performances:** the top single rounds, maps and matches, for all years, a year or a single tournament.
- **Stats:** every player's numbers for all years, a year or a tournament, with sortable columns.
- **Player pages:** each player's record by year, by tournament and for every match.

The scraper, database and model live in [vctstats](https://github.com/bernielaird/vctstats). This site only reads a small read-only SQLite file that the project exports (`vct_site.sqlite`, about 40 MB).

## MusicElo (`/musicelo/`)

Rank your music by picking between two songs at a time, with Elo ratings, Spotify imports and user accounts. Its code lives in the [MusicElo](https://github.com/bernielaird/MusicElo) repo; this site installs it as a package (the last line of `requirements.txt`) and mounts its `songs` app at `/musicelo/`, so both run as one Render service. To pick up MusicElo changes, push to its `main` and redeploy this site.

## Stack

- **Backend:** Python, Django 6.1
- **Frontend:** HTML and CSS templates, plain JavaScript, Chart.js for the win-probability charts
- **Data:** SQLite (read-only) for `/vct/`; PostgreSQL for MusicElo's accounts and rankings
- **Hosting:** Render (gunicorn) with WhiteNoise serving static files

## Project layout

```
mysite/          Django settings and root URLs
mainsite/        Home, about, projects, contact
  static/        styles.css (colors for both themes), theme.js, the font, images
  templates/
vct/             The VCT app
  data.py        Read-only queries on data/vct_site.sqlite
  views.py, urls.py
  fetch_data.py  Downloads the data file at build time
  templates/vct/ Overview, matches, match, round, best performances, stats, player pages
  static/vct/    vct.css, sort.js
  data/          vct_site.sqlite (downloaded, not in git)
```

## Running locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python vct/fetch_data.py            # downloads the /vct/ data file (~13 MB compressed)
```

Create a `.env` file in the project root (git ignores it):

```
SECRET_KEY=any-long-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
# Optional, for MusicElo's Spotify features:
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8000/musicelo/callback/
```

Without `DATABASE_URL`, MusicElo's accounts go in a local `db.sqlite3`; run `python manage.py migrate` once first.

Then run:

```powershell
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Deployment

Render deploys from `main`. Build command:

```
pip install -r requirements.txt && python vct/fetch_data.py && python manage.py collectstatic --noinput && python manage.py migrate
```

Render's environment settings provide `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `DATABASE_URL` (MusicElo's Postgres) and the `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET` and `SPOTIPY_REDIRECT_URI` (`https://www.bernielaird.com/musicelo/callback/`) for MusicElo.

### How `/vct/` data stays current

The data file isn't committed, because it changes with every new match and would bloat git history. Instead:

1. The vctstats project scrapes new matches, rebuilds its database and model, and exports `vct_site.sqlite` (`update_site.ps1`, run by a scheduled task whenever no update has finished in the last 24 hours).
2. It uploads the file, gzipped, to the `site-data` release on the vctstats repo, then calls Render's deploy hook.
3. During the build, `vct/fetch_data.py` downloads the file and checks that it opens. If anything fails, the build fails and Render keeps serving the previous version.

## Credits

- Font: TSTAR Mono Round, from [onlinewebfonts.com](http://www.onlinewebfonts.com) (CC BY 4.0)
- Match data: [vlr.gg](https://www.vlr.gg)
