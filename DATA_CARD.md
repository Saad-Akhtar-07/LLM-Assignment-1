# Urdu corpus data card

Generated: 2026-10-11. Sizes are decimal MB (1 MB = 1,000,000 bytes).

| Source / genre | URL | Licence / terms | Collection date | Raw MB | Cleaned MB | Documents |
|---|---|---|---|---:|---:|---:|
| wikipedia / encyclopedia | https://ur.wikipedia.org/ | CC BY-SA 4.0 / GFDL; page notices may vary | 2026-10-11 | 546.15 | 23.94 | 1,895 |
| wikisource / literature | https://ur.wikisource.org/ | Page-specific public-domain/free-license status; verify before reuse | 2026-10-11 | 224.39 | 28.32 | 3,478 |
| cc100 / general web | https://data.statmt.org/cc-100/ur.txt.xz | No IP claim for corpus preparation; underlying web copyrights vary | 2026-10-11 | 750.02 | 730.75 | 232,423 |

**Totals:** 783.01 MB cleaned text; 237,796 documents; 93,849,026 whitespace-delimited words; 1,426,451 unique words.

**Splits:** train 232,981 docs / 765.78 MB; val 2,380 docs / 8.42 MB; test 2,435 docs / 8.81 MB. Document-level hash split with seed 42 (98/1/1 target); Wikisource chapters are grouped by work title.

## Cleaning (measured UTF-8 text bytes)

| Step | Bytes before | Bytes after | Removed MB |
|---|---:|---:|---:|
| Markup/HTML/control extraction | 1,520,563,064 | 803,724,991 | 716.84 |
| Unicode normalization | 803,724,991 | 803,096,392 | 0.63 |
| Urdu line filter and contact redaction | 803,096,392 | 798,940,435 | 4.16 |
| Short-document rejection and exact deduplication | 798,940,435 | 792,974,172 | 5.97 |
| Repeated short boilerplate lines | 792,974,172 | 783,015,912 | 9.96 |
| Final duplicate and short-document check | 783,015,912 | 783,008,663 | 0.01 |

## Decisions and limits

Arabic yeh/kaf/heh variants map to Urdu forms; do-chashmi heh and ZWNJ remain distinct; Arabic/Urdu digits map to ASCII. Lines need at least 60% Urdu/Arabic-script letters, while natural English code-mixing remains.

CC-100 is web text with variable quality and unclear page-level redistribution rights. Its preparation claims no IP; the underlying pages retain their own rights. Wikimedia pages have page-specific notices. Keep this corpus within the course.

General web text dominates by size. Large Wikipedia biographies and Wikisource religious works may be overrepresented; poetry and contemporary dialogue are thinner. Language filtering can remove bilingual or Roman Urdu passages. Exact hashing does not catch paraphrases or near duplicates. Verify individual Wikisource work rights before redistribution.

Evidence: `metadata/documents.csv` lists document URLs and splits; `data/raw/{wikipedia,wikisource}/scrape_state.json` records website collection; `data/raw/cc100/state.json` records corpus provenance; `metadata/cleaning_stats.json` has exact counts.
