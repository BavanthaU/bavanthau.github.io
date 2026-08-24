#!/usr/bin/env python3
"""Preview server that answers Range requests, which `python3 -m http.server` does not.

    python3 tools/serve.py [port]        # default 8000

Use this rather than the plain module when a watch page is being checked. Seeking in a
video, and therefore every chapter link and every `#t=` deep link, needs partial content;
`http.server` ignores the Range header and returns the whole file with a 200, so a seek past
what the browser happens to hold silently snaps back to the start. GitHub Pages serves
ranges, so that failure only ever appears in local preview.

Python 3 standard library only, like everything else in tools/.
"""

import http.server
import os
import re
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
        if not m or (not m.group(1) and not m.group(2)):
            f.close()
            return super().send_head()

        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:                                   # bytes=-N, the last N bytes
            start = max(size - int(m.group(2)), 0)
            end = size - 1
        end = min(end, size - 1)

        if start >= size or start > end:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(64 * 1024, remaining))
            if not chunk:
                break
            self.wfile.write(chunk)
            remaining -= len(chunk)
        f.close()
        return None

    def end_headers(self):
        # announced on every response, including the first 200, or a browser has no reason
        # to try a range at all
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), RangeHandler) as httpd:
        print(f"serving {ROOT} with Range support at http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
