"""One-time queue refresh after new title seeds are added."""

import argparse
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {"wikipedia": "ur.wikipedia.org", "wikisource": "ur.wikisource.org"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("site", choices=HOSTS)
    args = p.parse_args()
    folder = ROOT / "data" / "raw" / args.site
    frontier = folder / "scrape_frontier.jsonl"
    urls = set()
    if frontier.exists():
        with frontier.open(encoding="utf-8") as f:
            urls.update(json.loads(line)["url"] for line in f)
    added = 0
    with (folder / "titles.txt").open(encoding="utf-8") as f:
        for number, title in enumerate(f):
            if args.site == "wikipedia" and (number % 30 or added >= 50000):
                continue
            title = title.strip().replace(" ", "_")
            if title and ":" not in title and not title.startswith("#"):
                url = f"https://{HOSTS[args.site]}/wiki/{quote(title, safe='/')}"
                if url not in urls:
                    urls.add(url)
                    added += 1
    size = {}
    lengths = folder / "long_titles.tsv"
    if lengths.exists():
        with lengths.open(encoding="utf-8") as f:
            for row in f:
                length, title = row.rstrip("\n").split("\t", 1)
                if "فہرست" in title:
                    continue
                url = f"https://{HOSTS[args.site]}/wiki/{quote(title, safe='/')}"
                urls.add(url)
                size[url] = max(size.get(url, 0), int(length))
    # Big known documents first. Unknown dump titles retain a deterministic
    # lexicographic order after them.
    ordered = sorted(urls, key=lambda url: (-size.get(url, 0), url))
    temp = frontier.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        for url in ordered:
            f.write(json.dumps({"url": url}, ensure_ascii=False) + "\n")
    temp.replace(frontier)
    print(f"Queued {len(ordered)} titles for {args.site}; {len(size)} have size hints")


if __name__ == "__main__":
    main()
