"""Download official Wikimedia main-namespace title dumps for scrape seeds."""

import argparse
import gzip
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
WIKIS = {"wikipedia": "urwiki", "wikisource": "urwikisource"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("site", choices=WIKIS)
    p.add_argument("--contact", required=True)
    args = p.parse_args()
    wiki = WIKIS[args.site]
    url = f"https://dumps.wikimedia.org/{wiki}/latest/{wiki}-latest-all-titles-in-ns0.gz"
    out_dir = ROOT / "data" / "raw" / args.site
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "titles.txt"
    if output.exists():
        raise SystemExit(f"{output} already exists")
    response = requests.get(url, stream=True, timeout=60, headers={
        "User-Agent": f"UrduBPECourseCorpus/1.0 ({args.contact})"})
    response.raise_for_status()
    response.raw.decode_content = False
    count = 0
    with gzip.GzipFile(fileobj=response.raw) as source, output.open("w", encoding="utf-8", newline="\n") as sink:
        for raw in source:
            title = raw.decode("utf-8", errors="replace").strip()
            if title:
                sink.write(title + "\n")
                count += 1
    print(f"Saved {count} main-namespace titles from {url}")


if __name__ == "__main__":
    main()
