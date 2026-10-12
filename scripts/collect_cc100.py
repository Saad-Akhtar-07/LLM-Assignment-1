"""Stream CC-100 Urdu documents into provenance-preserving JSONL."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import lzma
from pathlib import Path

import requests


URL = "https://data.statmt.org/cc-100/ur.txt.xz"
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--target-mb", type=float, default=600, help="Raw UTF-8 document text target")
    args = p.parse_args()
    out_dir = ROOT / "data" / "raw" / "cc100"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "records.jsonl"
    if out.exists():
        raise SystemExit(f"{out} exists; move or delete it before restarting")
    session = requests.Session()
    session.headers["User-Agent"] = "UrduBPECourseCorpus/1.0 (educational research)"
    total = 0
    count = 0
    response = session.get(URL, stream=True, timeout=90)
    response.raise_for_status()
    response.raw.decode_content = False
    with lzma.LZMAFile(response.raw) as source, out.open("w", encoding="utf-8", newline="\n") as sink:
        parts = []
        while total < args.target_mb * 1_000_000:
            line = source.readline()
            if not line:
                break
            if line.strip():
                parts.append(line.decode("utf-8", errors="replace").strip())
                continue
            if not parts:
                continue
            raw = "\n".join(parts)
            parts.clear()
            nbytes = len(raw.encode("utf-8"))
            record = {"id": f"cc100:{count}", "source": "cc100", "genre": "general_web",
                      "title": "", "url": URL, "collected_at": datetime.now(timezone.utc).isoformat(),
                      "license": "CC-100 preparation: no IP claim; underlying pages retain copyright",
                      "raw_bytes": nbytes, "text": raw}
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            total += nbytes
            if count % 10000 == 0:
                print(f"CC-100: {count} documents, {total / 1e6:.1f} MB raw", flush=True)
        if parts and total < args.target_mb * 1_000_000:
            raw = "\n".join(parts)
            sink.write(json.dumps({"id": f"cc100:{count}", "source": "cc100",
                                   "genre": "general_web", "title": "", "url": URL,
                                   "collected_at": datetime.now(timezone.utc).isoformat(),
                                   "license": "CC-100 preparation: no IP claim; underlying pages retain copyright",
                                   "raw_bytes": len(raw.encode("utf-8")), "text": raw}, ensure_ascii=False) + "\n")
            count += 1
            total += len(raw.encode("utf-8"))
    with out.open("rb") as verification_stream:
        checksum = hashlib.file_digest(verification_stream, "sha256").hexdigest()
    (out_dir / "state.json").write_text(json.dumps({"url": URL, "documents": count,
        "raw_text_bytes": total, "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "sha256_records": checksum}, indent=2), encoding="utf-8")
    print(f"Complete: {count} documents, {total / 1e6:.1f} MB raw")


if __name__ == "__main__":
    main()
