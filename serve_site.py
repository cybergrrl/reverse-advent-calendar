#!/usr/bin/env python3
import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server(ThreadingHTTPServer):
    request_queue_size = 128


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    handler = functools.partial(NoCacheHandler, directory=str(Path(__file__).parent / "docs"))
    print(f"Calendar preview at http://localhost:{port}")
    Server(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
