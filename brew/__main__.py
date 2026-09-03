"""Run brew_tool:  python3 -m brew [--port 8765] [--lan] [--data DIR] [--no-open]"""
import argparse
import os
import socket
import webbrowser
from pathlib import Path

from .server import make_server

REPO = Path(__file__).resolve().parent.parent


def data_dir(arg=None):
    """--data, else $BREW_DATA, else <repo>/data."""
    return Path(arg or os.environ.get("BREW_DATA") or REPO / "data")


def lan_ip():
    """The address a phone on the same network would use for this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))      # no packets are sent
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main():
    p = argparse.ArgumentParser(description="brew_tool — recipe design and must prep")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--lan", action="store_true",
                   help="also answer phones on your network (binds 0.0.0.0)")
    p.add_argument("--data", default=None, help="where recipes and batches live")
    p.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = p.parse_args()
    ddir = data_dir(args.data)
    store = None
    try:
        from .store import Store
        store = Store(ddir)
    except ImportError:
        pass
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    srv = make_server(store, host, args.port)
    local = f"http://127.0.0.1:{args.port}/"
    print(f"brew_tool — {local}")
    if args.lan:
        print(f"On your phone: http://{lan_ip()}:{args.port}/  "
              "(anyone on this network can use it — no login)")
    print(f"Data: {ddir}  (Ctrl-C to stop)")
    if not args.no_open:
        webbrowser.open(local)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
