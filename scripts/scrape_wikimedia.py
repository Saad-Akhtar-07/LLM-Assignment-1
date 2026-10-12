"""Scrape robots-allowed /wiki/ pages, using dump titles as crawl seeds."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote, unquote, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {"wikipedia": "ur.wikipedia.org", "wikisource": "ur.wikisource.org"}
GENRES = {"wikipedia": "encyclopedia", "wikisource": "literature"}
DROP = "script,style,form,footer,aside,table,figure,.mw-editsection,.reference,.reflist,.navbox,.toc,.metadata,.noprint,.catlinks"
BLOCKS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "section", "blockquote"}
THREAD = threading.local()
RATE_LOCK = threading.Lock()
NEXT_REQUEST = 0.0


def canonical(host, title):
    title = title.replace(" ", "_").strip()
    if not title or ":" in title or title.startswith("#"):
        return None
    return f"https://{host}/wiki/{quote(title, safe='/')}"


def fetch(url, agent, interval):
    global NEXT_REQUEST
    if not hasattr(THREAD, "session"):
        THREAD.session = requests.Session()
        THREAD.session.headers.update({"User-Agent": agent, "Accept-Encoding": "gzip"})
    for attempt in range(6):
        with RATE_LOCK:
            delay = max(0, NEXT_REQUEST - time.monotonic())
            NEXT_REQUEST = max(NEXT_REQUEST, time.monotonic()) + interval
        if delay:
            time.sleep(delay)
        try:
            response = THREAD.session.get(url, timeout=45)
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 60)))
                continue
            if response.status_code >= 500:
                time.sleep(900)  # Wikimedia robot policy after server errors.
                continue
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            body = soup.select_one("#mw-content-text .mw-parser-output") or soup.select_one("#mw-content-text")
            if body is None:
                return None
            links = []
            for tag in body.select('a[href^="/wiki/"]'):
                path = urlsplit(tag.get("href", "")).path
                title = unquote(path.removeprefix("/wiki/")).replace("_", " ")
                link = canonical(urlsplit(url).netloc, title)
                if link:
                    links.append(link)
            for tag in list(body.select(DROP)):
                tag.decompose()
            for tag in list(body.find_all(BLOCKS)):
                if tag.name == "br":
                    tag.replace_with("\n")
                else:
                    tag.insert_before("\n")
            text = body.get_text(" ", strip=False)
            text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
            text = re.sub(r"[ \t]+", " ", text).strip()
            return text, links, len(response.content)
        except requests.RequestException:
            if attempt == 5:
                return None
            time.sleep(2 ** attempt)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("site", choices=HOSTS)
    p.add_argument("--contact", required=True)
    p.add_argument("--target-mb", type=float, default=60)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--interval", type=float, default=0.35, help="Minimum seconds between requests")
    args = p.parse_args()
    host = HOSTS[args.site]
    agent = f"UrduBPECourseCorpus/1.0 ({args.contact})"
    out_dir = ROOT / "data" / "raw" / args.site
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "scraped_records.jsonl"
    frontier_path = out_dir / "scrape_frontier.jsonl"
    robot_response = requests.get(f"https://{host}/robots.txt", headers={"User-Agent": agent}, timeout=30)
    robot_response.raise_for_status()
    robots = RobotFileParser()
    robots.parse(robot_response.text.lstrip("\ufeff").splitlines())
    if not robots.can_fetch(agent, f"https://{host}/wiki/Test"):
        raise SystemExit("robots.txt disallows /wiki/ for this User-Agent")
    seen = set()
    bytes_done = 0
    pages = 0
    if out.exists():
        with out.open(encoding="utf-8") as f:
            for row in f:
                rec = json.loads(row)
                seen.add(rec["url"])
                bytes_done += len(rec["text"].encode("utf-8"))
                pages += 1
    frontier = deque()
    queued = set(seen)
    if frontier_path.exists():
        with frontier_path.open(encoding="utf-8") as f:
            for row in f:
                url = json.loads(row)["url"]
                if url not in queued:
                    frontier.append(url)
                    queued.add(url)
    else:
        seeds = out_dir / "titles.txt"
        if not seeds.exists():
            raise SystemExit(f"Missing seed titles: {seeds}; run download_wikimedia_titles.py")
        with seeds.open(encoding="utf-8") as f, frontier_path.open("w", encoding="utf-8") as ff:
            for number, title in enumerate(f):
                if args.site == "wikipedia" and number % 30:
                    continue
                if args.site == "wikipedia" and len(frontier) >= 50000:
                    break
                url = canonical(host, title)
                if url and url not in queued:
                    frontier.append(url)
                    queued.add(url)
                    ff.write(json.dumps({"url": url}, ensure_ascii=False) + "\n")
    with out.open("a", encoding="utf-8", newline="\n") as sink, frontier_path.open("a", encoding="utf-8", newline="\n") as frontier_file, ThreadPoolExecutor(max_workers=args.workers) as pool:
        active = {}
        while (frontier or active) and bytes_done < args.target_mb * 1_000_000:
            while frontier and len(active) < args.workers:
                url = frontier.popleft()
                if url in seen or not robots.can_fetch(agent, url):
                    continue
                active[pool.submit(fetch, url, agent, args.interval)] = url
            if not active:
                break
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                url = active.pop(future)
                seen.add(url)
                result = future.result()
                if not result:
                    continue
                text, links, html_bytes = result
                if len(text) < 150:
                    continue
                title = unquote(urlsplit(url).path.removeprefix("/wiki/")).replace("_", " ")
                rec = {"id": f"scraped:{args.site}:{pages}", "source": args.site,
                       "genre": GENRES[args.site], "title": title, "url": url,
                       "collected_at": datetime.now(timezone.utc).isoformat(),
                       "license": "CC BY-SA 4.0 / GFDL; check page-specific notices",
                       "raw_bytes": html_bytes, "text": text}
                sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
                bytes_done += len(text.encode("utf-8"))
                pages += 1
                if pages % 100 == 0:
                    sink.flush()
                    print(f"{args.site}: {pages} scraped pages, {bytes_done/1e6:.2f} MB text", flush=True)
                for link in links:
                    if link not in queued and robots.can_fetch(agent, link) and len(queued) < 200000:
                        queued.add(link)
                        frontier.append(link)
                        frontier_file.write(json.dumps({"url": link}, ensure_ascii=False) + "\n")
            frontier_file.flush()
    (out_dir / "scrape_state.json").write_text(json.dumps({"pages": pages, "text_bytes": bytes_done,
        "robots_url": f"https://{host}/robots.txt", "allowed_path": "/wiki/",
        "user_agent": agent, "date": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    print(f"Complete: {pages} scraped pages, {bytes_done/1e6:.2f} MB text")


if __name__ == "__main__":
    main()
