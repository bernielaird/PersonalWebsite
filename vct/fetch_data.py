"""Download the /vct/ data file during the build (it isn't in git).

Render build command:
    pip install -r requirements.txt && python vct/fetch_data.py && python manage.py collectstatic --noinput

Downloads VCT_DATA_URL (default: the vctstats release asset) to vct/data/vct_site.sqlite, checks it opens,
then swaps it in. Any failure exits non-zero, so the build fails and Render keeps the previous deploy.

Locally: `python vct/fetch_data.py` gets the published file; if you already have one (e.g. copied from
vct-ratings/data/exports/), you don't need to run it.
"""
import gzip
from contextlib import closing
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://github.com/bernielaird/vctstats/releases/download/site-data/vct_site.sqlite.gz"
DEST = Path(__file__).resolve().parent / "data" / "vct_site.sqlite"


def main():
    url = os.environ.get("VCT_DATA_URL") or DEFAULT_URL
    DEST.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DEST.parent, suffix=".download")
    os.close(fd)
    try:
        print(f"Downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalWebsite build"})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as out:
            src = gzip.GzipFile(fileobj=r) if url.endswith(".gz") else r
            shutil.copyfileobj(src, out)
        with closing(sqlite3.connect(f"file:{Path(tmp).as_posix()}?mode=ro", uri=True)) as c:
            meta = dict(c.execute("SELECT key, value FROM meta"))
        os.replace(tmp, DEST)
        print(f"Saved {DEST} ({DEST.stat().st_size / 1e6:.1f} MB): {meta.get('matches')} matches, "
              f"built {meta.get('built')}")
    except Exception as e:  # noqa: BLE001  any failure should fail the build
        sys.exit(f"Could not get the VCT data file: {e}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


if __name__ == "__main__":
    main()
