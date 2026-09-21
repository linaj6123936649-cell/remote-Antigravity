# -*- coding: utf-8 -*-
"""Detached background launcher for RemoteCoder.
Launches pythonw with CREATE_NO_WINDOW and DETACHED_PROCESS flags,
ensuring zero visible console or terminal windows on Windows 10/11.
"""
import os
import subprocess
import sys
import time
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

def get_pythonw():
    # 1. Check local virtualenv
    local_pyw = os.path.join(ROOT_DIR, ".venv", "Scripts", "pythonw.exe")
    if os.path.exists(local_pyw):
        return local_pyw

    # 2. Check current interpreter
    curr_exe = sys.executable
    curr_pyw = curr_exe.replace("python.exe", "pythonw.exe")
    if os.path.exists(curr_pyw):
        return curr_pyw

    # 3. Check shared parent flagship virtualenv
    parent = os.path.dirname(ROOT_DIR)
    for d in os.listdir(parent):
        if "Antigravity" in d:
            flag_dir = os.path.join(parent, d)
            for sub in os.listdir(flag_dir):
                if "Agent" in sub:
                    shared = os.path.join(flag_dir, sub, ".venv", "Scripts", "pythonw.exe")
                    if os.path.exists(shared):
                        return shared

    return "pythonw"

def stop_previous_port():
    try:
        # Check port 8080 and kill process
        cmd = 'powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"'
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        if out:
            pids = set(out.split())
            for pid in pids:
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            time.sleep(1)
    except Exception:
        pass

def main():
    stop_previous_port()
    pyw = get_pythonw()

    # CREATE_NO_WINDOW (0x08000000) | DETACHED_PROCESS (0x00000008)
    flags = 0x08000000 | 0x00000008

    proc = subprocess.Popen(
        [pyw, "-m", "app.server"],
        cwd=ROOT_DIR,
        creationflags=flags,
        close_fds=True
    )

    # Poll health
    ready = False
    for _ in range(25):
        time.sleep(0.3)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass

    if ready:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
