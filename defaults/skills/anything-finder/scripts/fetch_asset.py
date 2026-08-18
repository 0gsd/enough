#!/usr/bin/env python3
"""
fetch_asset.py — Download an image or file with a normal browser User-Agent, save it to
the skill's output directory, and write a provenance sidecar recording where it came from
and under what license/attribution. Use for cleared images, fonts, textures, samples,
manuals, and any file-return find, so the rights travel with the file.

Run it from the project directory; the default output path is relative to there
(rness/io/output/anything-finder/), or pass --outdir. This is a narrow file-download
helper, not a general web transport — read pages with the harness's fetch_url tool.

Setting a browser User-Agent is a legal, ordinary part of HTTP — it just makes hosts that
reject blank/botty agents serve the same public file they'd serve any visitor. Use it only
for content the user has a right to obtain.

Examples:
  python3 rness/skills/anything-finder/scripts/fetch_asset.py --url "https://upload.wikimedia.org/.../plate.jpg" \
      --name botanical_plate --license CC0 \
      --attribution "Biodiversity Heritage Library, public domain" \
      --source "https://www.biodiversitylibrary.org/page/12345"

  python3 rness/skills/anything-finder/scripts/fetch_asset.py --url "https://fonts.example/Foo.otf" --name Foo-Regular \
      --license "SIL OFL 1.1" --source "https://velvetyne.fr/fonts/foo/"
"""
import argparse
import datetime
import mimetypes
import os
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/122.0 Safari/537.36 anything-finder/1.0")
OUTDIR = "rness/io/output/anything-finder"

EXT_BY_MIME = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg", "image/tiff": ".tif",
    "application/pdf": ".pdf", "font/otf": ".otf", "font/ttf": ".ttf",
    "application/zip": ".zip", "audio/wav": ".wav", "audio/mpeg": ".mp3",
    "audio/x-wav": ".wav", "audio/flac": ".flac",
}


def guess_ext(url, content_type):
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in EXT_BY_MIME:
            return EXT_BY_MIME[ct]
        guessed = mimetypes.guess_extension(ct)
        if guessed:
            return guessed
    base = url.split("?")[0].rsplit("/", 1)[-1]
    if "." in base:
        return "." + base.rsplit(".", 1)[-1].lower()
    return ".bin"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="direct URL to the file")
    ap.add_argument("--name", required=True, help="base filename (no extension needed)")
    ap.add_argument("--license", default="UNKNOWN",
                    help='e.g. "CC0", "PD", "CC-BY-4.0", "SIL OFL 1.1", "MIT"')
    ap.add_argument("--attribution", default="",
                    help="credit string to reproduce, if the license requires it")
    ap.add_argument("--source", default="",
                    help="the human-readable source/reference page URL")
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--ua", default=UA, help="override User-Agent")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    req = urllib.request.Request(a.url, headers={
        "User-Agent": a.ua,
        "Accept": "*/*",
        "Referer": a.source or a.url,
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[http {e.code}] {a.url} — {e.reason}. "
                         f"The host may block this agent, require a referer/cookie, or "
                         f"the file may be gone; try the source page or a Wayback copy.")
    except urllib.error.URLError as e:
        raise SystemExit(f"[network] Could not reach {a.url}: {getattr(e,'reason',e)}. "
                         f"If the host is blocked by the environment, ask the user to "
                         f"allowlist it.")

    ext = guess_ext(a.url, ctype)
    fname = a.name if a.name.lower().endswith(ext) else a.name + ext
    fpath = os.path.join(a.outdir, fname)
    with open(fpath, "wb") as f:
        f.write(data)

    prov = os.path.join(a.outdir, a.name + ".provenance.txt")
    with open(prov, "w") as f:
        f.write("anything-finder — asset provenance\n")
        f.write("=" * 40 + "\n")
        f.write(f"file        : {fname}\n")
        f.write(f"bytes       : {len(data)}\n")
        f.write(f"content-type: {ctype}\n")
        f.write(f"download-url: {a.url}\n")
        f.write(f"source-page : {a.source}\n")
        f.write(f"license     : {a.license}\n")
        f.write(f"attribution : {a.attribution}\n")
        f.write(f"retrieved   : {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        if a.license.upper() in ("CC0", "PD", "PUBLIC DOMAIN"):
            f.write("note        : no attribution legally required, but recording source anyway.\n")
        elif a.attribution:
            f.write("note        : reproduce the attribution string when using this asset.\n")
        else:
            f.write("note        : license may require attribution — confirm on the source page.\n")

    print(f"saved  : {fpath} ({len(data)} bytes, {ctype or 'unknown type'})")
    print(f"prov   : {prov}")
    print(f"license: {a.license}" + (f"  | credit: {a.attribution}" if a.attribution else ""))


if __name__ == "__main__":
    main()
