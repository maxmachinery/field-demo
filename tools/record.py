#!/usr/bin/env python3
"""Record the field demo with Playwright (Chromium).

  python3 tools/record.py            # desktop + mobile videos, og.png, check shots
  python3 tools/record.py --skip-og  # videos only

Outputs (video/ is gitignored):
  video/raw/desktop.webm      1280x720, one full 73 s run
  video/raw/mobile.webm       390x844,  one full 73 s run
  video/shots/t{4,18,28,41,49,58,66}.png frames
  public/og.png               1200x630 share image, the corrected Cause
Then run tools/make-video.sh to produce the mp4s and the gif.
"""
import argparse
import functools
import http.server
import pathlib
import shutil
import socketserver
import sys
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
VIDEO = ROOT / "video"
LOOP_MS = 73_000          # 69 s run, plus 4 s holding on the end card
SHOTS_MS = (4_000, 18_000, 28_000, 41_000, 49_000, 58_000, 66_000)
OG_MS = 49_000            # the corrected Cause


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/" % httpd.server_address[1]


def record(browser, base, name, width, height, mobile=False):
    """One clean pass: no screenshots, so nothing stalls the video compositor."""
    out = VIDEO / "raw" / name
    if out.exists():
        shutil.rmtree(out)
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        is_mobile=mobile,
        has_touch=mobile,
        record_video_dir=str(out),
        record_video_size={"width": width, "height": height},
    )
    page = ctx.new_page()
    page.goto(base, wait_until="load")
    started = time.monotonic()
    left = LOOP_MS / 1000 - (time.monotonic() - started)
    page.wait_for_timeout(left * 1000)
    ctx.close()                          # flushes the video file
    webm = next(out.glob("*.webm"))
    final = VIDEO / "raw" / ("%s.webm" % name)
    if final.exists():
        final.unlink()
    webm.rename(final)
    shutil.rmtree(out)
    print("recorded %s (%dx%d)" % (final.relative_to(ROOT), width, height))


def frames(browser, base, marks):
    """Verification stills, on their own run so the video never sees them."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(base, wait_until="load")
    started = time.monotonic()
    (VIDEO / "shots").mkdir(parents=True, exist_ok=True)
    for mark in marks:
        left = mark / 1000 - (time.monotonic() - started)
        if left > 0:
            page.wait_for_timeout(left * 1000)
        page.screenshot(path=str(VIDEO / "shots" / ("t%d.png" % (mark // 1000))))
    ctx.close()
    print("wrote %d frames to video/shots" % len(marks))


def og_image(browser, base):
    ctx = browser.new_context(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(base, wait_until="load")
    page.wait_for_timeout(OG_MS)
    # frame the share image on the top of the gap message rather than the tail of the thread
    page.evaluate(
        "() => { const m = [...document.querySelectorAll('#threadBody .msg.in')].pop();"
        " const c = document.getElementById('threadBody');"
        " if (m) c.scrollTop += m.getBoundingClientRect().top - c.getBoundingClientRect().top - 8; }"
    )
    page.wait_for_timeout(120)
    page.screenshot(path=str(PUBLIC / "og.png"))
    ctx.close()
    print("wrote public/og.png (1200x630)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-og", action="store_true")
    ap.add_argument("--skip-video", action="store_true")
    args = ap.parse_args()

    (VIDEO / "raw").mkdir(parents=True, exist_ok=True)
    httpd, base = serve(PUBLIC)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            if not args.skip_video:
                record(browser, base, "desktop", 1280, 720)
                record(browser, base, "mobile", 390, 844, mobile=True)
                frames(browser, base, SHOTS_MS)
            if not args.skip_og:
                og_image(browser, base)
            browser.close()
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
