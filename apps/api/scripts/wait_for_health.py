"""PharmaTrust - Wait for Backend Health Check to be ready.
Polls http://127.0.0.1:8000/api/v1/health for up to max_wait_seconds.
Exits with 0 if ready, or 1 if timed out.
"""
import sys
import time
import urllib.request
import urllib.error

def wait_for_health(max_wait_seconds: int = 35, url: str = "http://127.0.0.1:8000/api/v1/health") -> bool:
    print(f"  - Dang tham do ket noi API tai {url} (toi da {max_wait_seconds}s)...")
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print("  - [OK] Backend FastAPI da san sang va ket noi CSDL thanh cong!")
                    return True
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError):
            pass
        time.sleep(1)
    print(f"  - [LOI] Backend khong phan hoi tren {url} sau {max_wait_seconds} giay!")
    return False

if __name__ == "__main__":
    success = wait_for_health()
    sys.exit(0 if success else 1)
