# TLC monthly files into data/raw/ with curl
import argparse
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CDN = "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{}.parquet"
OUT = Path("data/raw")


def months(first, last):
    y, m = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    while (y, m) <= (y1, m1):
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def get(month, tries=5):
    url = CDN.format(month)
    dest = OUT / f"fhvhv_tripdata_{month}.parquet"
    size = remote_size(url)
    if dest.exists() and dest.stat().st_size == size:
        return month, "skip", size, 0.0
    part = dest.with_suffix(".part")
    t0 = time.time()
    for _ in range(tries):
        # stalled transfer: drop and resume
        subprocess.run(["curl", "-s", "-C", "-", "--retry", "5", "--speed-limit", "50000",
                        "--speed-time", "60", "-o", str(part), url])
        if part.exists() and part.stat().st_size == size:
            part.replace(dest)
            return month, "done", size, time.time() - t0
    raise RuntimeError(f"{month}: incomplete after {tries} tries")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("first")
    p.add_argument("last")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(a.workers) as ex:
        for month, status, size, secs in ex.map(get, months(a.first, a.last)):
            print(month, status, f"{size / 1e6:.0f} MB", f"{secs:.0f}s", flush=True)


if __name__ == "__main__":
    main()
