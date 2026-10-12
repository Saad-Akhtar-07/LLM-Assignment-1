"""Get large main-namespace Urdu titles from official Wikimedia page SQL dumps."""

import argparse
import csv
import gzip
import heapq
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
WIKIS = {"wikipedia": "urwiki", "wikisource": "urwikisource"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site", choices=WIKIS)
    parser.add_argument("--contact", required=True)
    args = parser.parse_args()
    wiki = WIKIS[args.site]
    url = f"https://dumps.wikimedia.org/{wiki}/latest/{wiki}-latest-page.sql.gz"
    output = ROOT / "data" / "raw" / args.site / "long_titles.tsv"
    output.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=90, headers={
        "User-Agent": f"UrduBPECourseCorpus/1.0 ({args.contact})"})
    response.raise_for_status()
    response.raw.decode_content = False
    largest = []
    scanned = 0
    with gzip.GzipFile(fileobj=response.raw) as f:
        for raw in f:
            if not raw.startswith(b"("):
                continue
            line = raw.decode("utf-8", errors="replace").strip().rstrip(",;")
            try:
                fields = next(csv.reader([line[1:-1]], delimiter=",", quotechar="'", escapechar="\\"))
                if len(fields) < 10 or fields[1] != "0" or fields[3] != "0":
                    continue
                title = fields[2]
                size = int(fields[9])
                if not any(0x600 <= ord(c) <= 0x6FF for c in title) or size < 1000:
                    continue
            except (ValueError, IndexError, csv.Error):
                continue
            scanned += 1
            candidate = (size, title)
            if len(largest) < 10000:
                heapq.heappush(largest, candidate)
            elif candidate > largest[0]:
                heapq.heapreplace(largest, candidate)
    with output.open("w", encoding="utf-8", newline="\n") as sink:
        for size, title in sorted(largest, reverse=True):
            sink.write(f"{size}\t{title}\n")
    print(f"Scanned {scanned} content pages; saved {len(largest)} longest titles from {url}")


if __name__ == "__main__":
    main()
