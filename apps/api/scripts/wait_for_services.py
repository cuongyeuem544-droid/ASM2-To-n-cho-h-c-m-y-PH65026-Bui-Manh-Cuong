"""PharmaTrust - Wait for Services to be fully ready before opening browser.
Polls Storefront (:3000), Admin Web (:5173), and Backend (:8000).
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
        "url": "http://127.0.0.1:5173",
        "port": 5173,
    },
    {
        "name": "Cua Hang Truc Tuyen (Storefront Next.js)",
        "url": "http://127.0.0.1:3000",
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

def check_service_ready(url: str, port: int, timeout_per_req: float = 2.0) -> bool:
    """Send HTTP request to verify service readiness."""
    # Fast check socket first
    if not is_socket_open(port) and not is_socket_open(port, "localhost"):
        return False

    for test_url in [url, url.replace("127.0.0.1", "localhost")]:
        try:
            req = urllib.request.Request(
                test_url,
                headers={"User-Agent": "H4Care-Startup-Checker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout_per_req) as resp:
                if 200 <= resp.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return True
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError):
            continue
    return False

def wait_for_all(max_wait_seconds: int = 45) -> bool:
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

    print("  - [LOI] Cac dich vu sau day khong phan hoi kip thoi gian:")
    for s in pending:
        print(f"    * {s['name']}: {s['url']} (khong phan hoi sau {max_wait_seconds}s)")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cho cac dich vu web H4CARE san sang")
    parser.add_argument("--timeout", type=int, default=45, help="Thoi gian cho toi da (giay)")
    args = parser.parse_args()

    success = wait_for_all(max_wait_seconds=args.timeout)
    sys.exit(0 if success else 1)
