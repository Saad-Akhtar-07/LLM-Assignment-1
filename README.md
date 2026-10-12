# Part A: Urdu corpus

This workspace builds a UTF-8 Urdu corpus for the assignment. The source
documents stay under `data/raw/`; final document-level splits are
`data/final/train.txt`, `val.txt`, and `test.txt`.

Requirements: Python 3.10+, `requests`, `beautifulsoup4`.

```powershell
python -m pip install requests beautifulsoup4
python scripts/download_wikimedia_titles.py wikipedia --contact "YOUR_EMAIL"
python scripts/download_wikimedia_titles.py wikisource --contact "YOUR_EMAIL"
python scripts/download_long_titles.py wikipedia --contact "YOUR_EMAIL"
python scripts/download_long_titles.py wikisource --contact "YOUR_EMAIL"
python scripts/prioritize_frontier.py wikipedia
python scripts/prioritize_frontier.py wikisource
python scripts/scrape_wikimedia.py wikipedia --contact "YOUR_EMAIL" --target-mb 25
python scripts/scrape_wikimedia.py wikisource --contact "YOUR_EMAIL" --target-mb 45
python scripts/collect_cc100.py --target-mb 750
python scripts/build_corpus.py
python scripts/verify_corpus.py
```

The Wikimedia scrapers check robots.txt and collect through canonical `/wiki/`
article URLs. The title dump provides the crawl seeds. Subsequent runs resume
from the saved frontier.
CC-100 is streamed from the publisher and must be restarted if interrupted.
Rebuilding the splits is deterministic. `DATA_CARD.md` and
`metadata/cleaning_stats.json` are generated from measured bytes, never guessed.
`metadata/documents.csv` is a provenance and split manifest.

Do not redistribute the corpus outside the course: CC-100's underlying page
rights vary, and Wikisource pages can have work-specific notices.
