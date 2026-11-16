#!/usr/bin/env python3
"""Local dev server for the new site. `python3 app.py [port]`."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.webapp import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    print("RogFlix")
    print("  http://127.0.0.1:%d" % port)
    print("  http://<mac-ip>:%d" % port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
