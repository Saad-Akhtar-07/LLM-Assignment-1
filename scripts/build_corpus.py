"""Clean, deduplicate and split the three Urdu sources by whole document."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from normalize import normalize

END = "<|endoftext|>"
WORD = re.compile(r"\S+")
HTML = re.compile(r"<[^>]{1,300}>")
SPACE = re.compile(r"\s+")
BOILERPLATE = re.compile(
    r"(?:copyright|all rights reserved|privacy policy|اشتہار|تمام حقوق|"
    r"شیئر کریں|share this|مزید خبریں|متعلقہ خبریں)", re.IGNORECASE)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ().-]{7,}\d)(?!\d)")
SOCIAL = re.compile(r"(?:facebook\.com/|instagram\.com/|twitter\.com/|x\.com/|t\.me/|wa\.me/)", re.IGNORECASE)
SOURCES = ("wikipedia", "wikisource", "cc100")
SOURCE_URLS = {
    "wikipedia": "https://ur.wikipedia.org/",
    "wikisource": "https://ur.wikisource.org/",
    "cc100": "https://data.statmt.org/cc-100/ur.txt.xz",
}
LICENCES = {
    "wikipedia": "CC BY-SA 4.0 / GFDL; page notices may vary",
    "wikisource": "Page-specific public-domain/free-license status; verify before reuse",
    "cc100": "No IP claim for corpus preparation; underlying web copyrights vary",
}


def nbytes(s):
    return len(s.encode("utf-8"))


def urdu_ratio(line):
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return 0.0
    urdu = sum(0x600 <= ord(c) <= 0x6FF or 0x750 <= ord(c) <= 0x77F
               or 0x8A0 <= ord(c) <= 0x8FF for c in letters)
    return urdu / len(letters)


def clean_lines(text):
    kept = []
    for line in text.splitlines():
        line = SPACE.sub(" ", line).strip()
        if SOCIAL.search(line):
            continue
        line = EMAIL.sub("[email]", line)
        line = PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 10 else m.group(), line)
        if len(line) < 12 or urdu_ratio(line) < 0.6:
            continue
        if line.startswith(("http://", "https://")) or "@" in line and " " not in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def stage_documents(stage, stats):
    seen = set()
    line_docs = Counter()
    with stage.open("w", encoding="utf-8", newline="\n") as sink:
        for source in SOURCES:
            filename = "scraped_records.jsonl" if source in {"wikipedia", "wikisource"} else "records.jsonl"
            path = ROOT / "data" / "raw" / source / filename
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as raw:
                for row in raw:
                    rec = json.loads(row)
                    s = stats[source]
                    s["downloaded_documents"] += 1
                    s["raw_bytes"] += rec["raw_bytes"] if "raw_bytes" in rec else nbytes(rec["text"])
                    text = HTML.sub(" ", rec["text"]).replace(END, " ")
                    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c)[0] != "C" or c == "\u200c")
                    s["extracted_bytes"] += nbytes(text)
                    text = normalize(text)
                    s["normalized_bytes"] += nbytes(text)
                    text = clean_lines(text)
                    s["filtered_bytes"] += nbytes(text)
                    if nbytes(text) < 200:
                        continue
                    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if digest in seen:
                        s["exact_duplicates"] += 1
                        continue
                    seen.add(digest)
                    s["deduplicated_bytes"] += nbytes(text)
                    s["staged_documents"] += 1
                    line_docs.update(set(line for line in text.splitlines() if len(line) <= 100))
                    rec["text"] = text
                    sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return line_docs


def write_outputs(stage, stats, line_docs):
    final_dir = ROOT / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = ROOT / "metadata"
    meta_dir.mkdir(exist_ok=True)
    outputs = {name: (final_dir / f"{name}.txt").open("w", encoding="utf-8", newline="\n")
               for name in ("train", "val", "test")}
    seen = set()
    words = set()
    split_stats = Counter()
    total_words = 0
    with (meta_dir / "documents.csv").open("w", newline="", encoding="utf-8") as mf:
        writer = csv.DictWriter(mf, fieldnames=["id", "source", "genre", "title", "url", "collected_at", "license", "split", "bytes", "sha256"])
        writer.writeheader()
        with stage.open(encoding="utf-8") as src:
            for row in src:
                rec = json.loads(row)
                source = rec["source"]
                lines = [line for line in rec["text"].splitlines()
                         if not (len(line) <= 100 and
                                 ((line_docs[line] >= 10 and BOILERPLATE.search(line))
                                  or line_docs[line] >= 1000))]
                text = "\n".join(lines)
                stats[source]["after_boilerplate_bytes"] += nbytes(text)
                if nbytes(text) < 200:
                    continue
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if digest in seen:
                    stats[source]["post_boilerplate_duplicates"] += 1
                    continue
                seen.add(digest)
                # Keep chapters of one Wikisource work in the same split.
                group = rec.get("title", "").split("/")[0] if source == "wikisource" else digest
                bucket = int.from_bytes(hashlib.sha256(("42:" + group).encode()).digest()[:8], "big") % 100
                split = "train" if bucket < 98 else "val" if bucket == 98 else "test"
                outputs[split].write(text + "\n" + END + "\n")
                size = nbytes(text)
                split_stats[f"{split}_bytes"] += size
                split_stats[f"{split}_documents"] += 1
                stats[source]["final_bytes"] += size
                stats[source]["final_documents"] += 1
                tokens = WORD.findall(text)
                total_words += len(tokens)
                words.update(tokens)
                writer.writerow({k: rec.get(k, "") for k in writer.fieldnames if k not in {"split", "bytes", "sha256"}}
                                | {"split": split, "bytes": size, "sha256": digest})
    for handle in outputs.values():
        handle.close()
    return split_stats, total_words, len(words)


def write_card(stats, splits, word_count, unique_words):
    total = sum(s["final_bytes"] for s in stats.values())
    docs = sum(s["final_documents"] for s in stats.values())
    lines = ["# Urdu corpus data card", "", f"Generated: {date.today().isoformat()}. Sizes are decimal MB (1 MB = 1,000,000 bytes).", "",
             "| Source / genre | URL | Licence / terms | Collection date | Raw MB | Cleaned MB | Documents |",
             "|---|---|---|---|---:|---:|---:|"]
    for name in SOURCES:
        s = stats[name]
        lines.append(f"| {name} / {'encyclopedia' if name == 'wikipedia' else 'literature' if name == 'wikisource' else 'general web'} | {SOURCE_URLS[name]} | {LICENCES[name]} | {date.today().isoformat() if s['downloaded_documents'] else 'Not collected'} | {s['raw_bytes']/1e6:.2f} | {s['final_bytes']/1e6:.2f} | {s['final_documents']:,} |")
    lines += ["", f"**Totals:** {total/1e6:.2f} MB cleaned text; {docs:,} documents; {word_count:,} whitespace-delimited words; {unique_words:,} unique words.",
              "", "**Splits:** " + "; ".join(f"{name} {splits[f'{name}_documents']:,} docs / {splits[f'{name}_bytes']/1e6:.2f} MB" for name in ("train", "val", "test")) + ". Document-level hash split with seed 42 (98/1/1 target); Wikisource chapters are grouped by work title.",
              "", "## Cleaning (measured UTF-8 text bytes)", "",
              "| Step | Bytes before | Bytes after | Removed MB |", "|---|---:|---:|---:|"]
    steps = [("Markup/HTML/control extraction", "raw_bytes", "extracted_bytes"),
             ("Unicode normalization", "extracted_bytes", "normalized_bytes"),
             ("Urdu line filter and contact redaction", "normalized_bytes", "filtered_bytes"),
             ("Short-document rejection and exact deduplication", "filtered_bytes", "deduplicated_bytes"),
             ("Repeated short boilerplate lines", "deduplicated_bytes", "after_boilerplate_bytes"),
             ("Final duplicate and short-document check", "after_boilerplate_bytes", "final_bytes")]
    for label, before, after in steps:
        a = sum(s[before] for s in stats.values())
        b = sum(s[after] for s in stats.values())
        lines.append(f"| {label} | {a:,} | {b:,} | {(a-b)/1e6:.2f} |")
    lines += ["", "## Decisions and limits", "",
              "Arabic yeh/kaf/heh variants map to Urdu forms; do-chashmi heh and ZWNJ remain distinct; Arabic/Urdu digits map to ASCII. Lines need at least 60% Urdu/Arabic-script letters, while natural English code-mixing remains.",
              "", "CC-100 is web text with variable quality and unclear page-level redistribution rights. Its preparation claims no IP; the underlying pages retain their own rights. Wikimedia pages have page-specific notices. Keep this corpus within the course.",
              "", "General web text dominates by size. Large Wikipedia biographies and Wikisource religious works may be overrepresented; poetry and contemporary dialogue are thinner. Language filtering can remove bilingual or Roman Urdu passages. Exact hashing does not catch paraphrases or near duplicates. Verify individual Wikisource work rights before redistribution.",
              "", "Evidence: `metadata/documents.csv` lists document URLs and splits; `data/raw/{wikipedia,wikisource}/scrape_state.json` records website collection; `data/raw/cc100/state.json` records corpus provenance; `metadata/cleaning_stats.json` has exact counts.", ""]
    (ROOT / "DATA_CARD.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minimum-mb", type=float, default=500)
    args = p.parse_args()
    stats = defaultdict(Counter)
    stage = ROOT / "data" / "cleaned" / "staged.jsonl"
    stage.parent.mkdir(parents=True, exist_ok=True)
    line_docs = stage_documents(stage, stats)
    splits, word_count, unique_words = write_outputs(stage, stats, line_docs)
    write_card(stats, splits, word_count, unique_words)
    payload = {"sources": {k: dict(stats[k]) for k in SOURCES}, "splits": dict(splits),
               "words": word_count, "unique_words": unique_words,
               "cleaned_text_bytes": sum(s["final_bytes"] for s in stats.values())}
    (ROOT / "metadata" / "cleaning_stats.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"cleaned_mb": payload["cleaned_text_bytes"] / 1e6,
                      "sources": {k: stats[k]["final_bytes"] / 1e6 for k in SOURCES},
                      "splits": dict(splits)}, indent=2))
    if payload["cleaned_text_bytes"] < args.minimum_mb * 1_000_000:
        raise SystemExit(f"Below {args.minimum_mb} MB; collect more source text and rebuild")
    if sum(stats[s]["final_bytes"] > 0 for s in SOURCES) < 3:
        raise SystemExit("Fewer than three sources contributed cleaned documents")
    if stats["wikipedia"]["final_bytes"] + stats["wikisource"]["final_bytes"] < 50_000_000:
        raise SystemExit("Self-collected Wikimedia text is below 50 MB")


if __name__ == "__main__":
    main()
