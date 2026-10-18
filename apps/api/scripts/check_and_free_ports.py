"""PharmaTrust - Check and Free Ports (8000, 5173, 3000).
Prevents port collision, IDOR and zombie processes on Windows.
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import time

def find_pids_on_port(port: int) -> set[int]:
    """Find process IDs listening on a specific TCP port using netstat."""
    pids = set()
    try:
        cmd = ["netstat", "-ano", "-p", "tcp"]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            line = line.strip()
            # Expecting format: TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  12345
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                local_addr = parts[1]
                # Safely extract port using rsplit to avoid partial match (e.g. 28000 matching 8000)
                port_str = local_addr.rsplit(":", 1)[-1]
                if port_str == str(port):
                    try:
                        pid = int(parts[4])
                        if pid > 0 and pid != os.getpid():
                            pids.add(pid)
                    except ValueError:
                        pass
    except Exception as e:
        print(f"  [CANH BAO] Khong the chay netstat kiem tra cong {port}: {e}")
    return pids

def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    """Test if a port is free to bind."""
    if find_pids_on_port(port):
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False

def kill_orphaned_uvicorn_workers():
    """Clean up any detached/orphaned multiprocessing worker processes holding port 8000."""
    try:
        out = subprocess.check_output(
            'wmic process where "Name=\'python.exe\' and CommandLine like \'%multiprocessing.spawn%\'" get ProcessId,CommandLine',
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            line = line.strip()
            match = re.search(r"parent_pid=(\d+)", line)
            pid_match = re.search(r"(\d+)\s*$", line)
            if match and pid_match:
                parent_pid = int(match.group(1))
                worker_pid = int(pid_match.group(1))
                # Check if parent is alive
                res = subprocess.run(["tasklist", "/fi", f"PID eq {parent_pid}"], capture_output=True, text=True)
                if "INFO: No tasks" in res.stdout or f"{parent_pid}" not in res.stdout:
                    # Parent dead, terminate orphan worker
                    print(f"  - Phat hien worker mo coi PID {worker_pid} (parent {parent_pid} da chet). Dang giai phong...")
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(worker_pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def free_port(port: int, max_retries: int = 5) -> bool:
    """Ensure port is completely freed by killing any lingering process."""
    if is_port_free(port):
        print(f"  - Cong {port}: [TRONG] San sang hoat dong.")
        return True

    pids = find_pids_on_port(port)
    if not pids:
        # Check for orphaned uvicorn workers if it's port 8000
        if port == 8000:
            kill_orphaned_uvicorn_workers()
        for _ in range(max_retries):
            time.sleep(0.5)
            if is_port_free(port):
                print(f"  - Cong {port}: [TRONG] Da san sang.")
                return True
        print(f"  - [CANH BAO] Cong {port} chua duoc giai phong hoan toan.")
        return False

    for pid in pids:
        print(f"  - Cong {port}: Phat hien tien trinh cu (PID {pid}) dang chiem dung. Dang don dep...")
        try:
            # /F force, /T tree (kills process and child processes)
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            # If parent process was already terminated, kill orphan children
            if res.returncode != 0 and port == 8000:
                kill_orphaned_uvicorn_workers()
        except Exception as e:
            print(f"  [CANH BAO] Khong the taskkill PID {pid}: {e}")

    # Wait for OS to release port
    for _ in range(max_retries):
        time.sleep(0.5)
        if is_port_free(port):
            print(f"  - Cong {port}: [DA GIAI PHONG] Da don dep tien trinh cu thanh cong.")
            return True

    # Final attempt for port 8000
    if port == 8000:
        kill_orphaned_uvicorn_workers()
        time.sleep(1)
        if is_port_free(port):
            print(f"  - Cong {port}: [DA GIAI PHONG] Da giai phong thanh cong worker mo coi.")
            return True

    print(f"  - [LOI] Khong the giai phong cong {port} sau khi taskkill.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Kiem tra va giai phong cac cong mang cua PharmaTrust.")
    parser.add_argument("--ports", default="8000,5173,3000", help="Danh sach cac cong cach nhau boi dau phay (mac dinh: 8000,5173,3000)")
    args = parser.parse_args()

    ports_to_check = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    print(f"  - Kiem tra trang thai {len(ports_to_check)} cong mang ({', '.join(str(p) for p in ports_to_check)})...")

    all_ok = True
    for port in ports_to_check:
        if not free_port(port):
            all_ok = False

    if all_ok:
        print("  - [OK] Toan bo cac cong 8000, 5173, 3000 da san sang khoi dong sach se!")
        sys.exit(0)
    else:
        print("  - [CANH BAO] Mot so cong van con bi chiem dung. Vui long dong cac ung dung dang dung cong nay.")
        sys.exit(1)

if __name__ == "__main__":
    main()
