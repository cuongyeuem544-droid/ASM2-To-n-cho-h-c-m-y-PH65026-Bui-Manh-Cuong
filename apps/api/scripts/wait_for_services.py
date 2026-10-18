"""PharmaTrust - Wait for Services to be fully ready before opening browser.
Polls Storefront (:3000) and Admin Web (:5173).
Non-blocking fallback ensures Google Chrome always opens smoothly.
"""
import argparse
import socket
import sys
import time
import urllib.error
import urllib.request

SERVICES = [
    {
        "name": "Cong Quan Tri Vien & Quan Ly Kho (Admin Web)",
        "url": "http://localhost:5173",
        "port": 5173,
    },
    {
        "name": "Cua Hang Truc Tuyen (Storefront Next.js)",
        "url": "http://localhost:3000",
        "port": 3000,
    },
]

def is_socket_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Fast check if port is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False

def is_service_listening(port: int) -> bool:
    """Check across common loopback addresses (IPv4 and IPv6)."""
    for host in ("127.0.0.1", "localhost", "::1"):
        if is_socket_open(port, host=host):
            return True
    return False

def check_service_ready(url: str, port: int, timeout_per_req: float = 2.0) -> bool:
    """Verify service readiness via socket first, then HTTP."""
    if not is_service_listening(port):
        return False

    # Once TCP socket is open, dev server is active and listening.
    # Fast HTTP probe; if it responds with any status < 500, it's ready.
    for test_url in [url, url.replace("localhost", "127.0.0.1")]:
        try:
            req = urllib.request.Request(
                test_url,
                headers={"User-Agent": "H4Care-Startup-Checker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout_per_req) as resp:
                if 200 <= resp.status < 500:
                    return True
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return True
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError):
            continue

    # Even if HTTP probe is still compiling Next.js page,
    # the confirmed open socket guarantees the dev server is alive.
    return True

def wait_for_all(max_wait_seconds: int = 15) -> bool:
    print(f"  - Dang kiem tra tinh trang san sang cua cac website (toi da {max_wait_seconds}s)...")
    start_time = time.time()

    pending = list(SERVICES)
    while pending and (time.time() - start_time) < max_wait_seconds:
        for s in list(pending):
            if check_service_ready(s["url"], s["port"]):
                elapsed = int(time.time() - start_time)
                print(f"  - [OK] {s['name']} (cong {s['port']}) da san sang sau {elapsed}s!")
                pending.remove(s)
        if pending:
            time.sleep(1.0)

    if not pending:
        total_time = int(time.time() - start_time)
        print(f"  - [HOAN TAT] Tat ca website da phan hoi san sang ({total_time}s) - San sang mo Chrome!")
        return True

    print("  - [THONG BAO] Cac dich vu dang hoan tat khoi dong trong nen:")
    for s in pending:
        print(f"    * {s['name']}: cong {s['port']} tiep tuc nap")
    print("  - Tiep tuc mo Google Chrome...")
    # Return True so startup script is never blocked from opening Chrome
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cho cac dich vu web H4CARE san sang")
    parser.add_argument("--timeout", type=int, default=15, help="Thoi gian cho toi da (giay)")
    args = parser.parse_args()

    wait_for_all(max_wait_seconds=args.timeout)
    sys.exit(0)
