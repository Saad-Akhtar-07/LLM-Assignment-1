"""Verify Part A counts, UTF-8 files and document-level split manifest."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
END = "<|endoftext|>\n"


def main():
    stats = json.loads((ROOT / "metadata" / "cleaning_stats.json").read_text(encoding="utf-8"))
    manifest_counts = {"train": 0, "val": 0, "test": 0}
    hashes = set()
    source_bytes = {}
    works = {}
    with (ROOT / "metadata" / "documents.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["sha256"] not in hashes, "Duplicate cleaned document in manifest"
            hashes.add(row["sha256"])
            manifest_counts[row["split"]] += 1
            source_bytes[row["source"]] = source_bytes.get(row["source"], 0) + int(row["bytes"])
            if row["source"] in {"wikipedia", "wikisource"}:
                assert row["id"].startswith("scraped:"), "Unscraped Wikimedia text in final corpus"
            if row["source"] == "wikisource":
                work = row["title"].split("/")[0]
                if work in works:
                    assert works[work] == row["split"], "Wikisource work crosses splits"
                works[work] = row["split"]
    for split in manifest_counts:
        assert manifest_counts[split] > 0, f"{split} split is empty"
        path = ROOT / "data" / "final" / f"{split}.txt"
        count = 0
        with path.open(encoding="utf-8", newline="") as f:
            for line in f:
                if line == END:
                    count += 1
        assert count == manifest_counts[split], f"{split} has {count} separators but {manifest_counts[split]} documents"
        assert count == stats["splits"][f"{split}_documents"]
    assert sum(source_bytes.values()) == stats["cleaned_text_bytes"]
    assert source_bytes.get("wikipedia", 0) + source_bytes.get("wikisource", 0) >= 50_000_000
    assert stats["cleaned_text_bytes"] >= 500_000_000
    assert sum(value > 0 for value in source_bytes.values()) >= 3
    print(f"Verified {stats['cleaned_text_bytes']/1e6:.2f} MB, "
          f"{len(hashes):,} unique documents, 3 sources, "
          f"{(source_bytes['wikipedia']+source_bytes['wikisource'])/1e6:.2f} MB self-collected")


if __name__ == "__main__":
    main()
