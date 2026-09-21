# -*- coding: utf-8 -*-
import os

root = r"C:\Users\gongy\Desktop\AI_Agent生態系總庫\05_獨立任務引擎_RemoteCoder"
desktop = r"C:\Users\gongy\Desktop"

files = {
    os.path.join(root, "1-啟動RemoteCoder-Start.bat"): (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\start_server.ps1\"\r\n"
        "echo.\r\n"
        "echo ===================================================\r\n"
        "echo  [OK] Server is running in background!\r\n"
        "echo  Press any key to close this window.\r\n"
        "echo ===================================================\r\n"
        "echo.\r\n"
        "pause\r\n"
    ),
    os.path.join(root, "2-停止RemoteCoder-Stop.bat"): (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\stop_server.ps1\"\r\n"
        "echo.\r\n"
        "echo ===================================================\r\n"
        "echo  [OK] RemoteCoder server stopped.\r\n"
        "echo ===================================================\r\n"
        "echo.\r\n"
        "pause\r\n"
    ),
    os.path.join(root, "3-開啟RemoteCoder網頁.bat"): (
        "@echo off\r\n"
        "start http://localhost:8080\r\n"
    ),
    os.path.join(desktop, "【啟動】RemoteCoder遠端任務引擎.bat"): (
        "@echo off\r\n"
        "setlocal\r\n"
        f"cd /d \"{root}\"\r\n"
        "call \"1-啟動RemoteCoder-Start.bat\"\r\n"
    ),
    os.path.join(desktop, "【停止】RemoteCoder遠端任務引擎.bat"): (
        "@echo off\r\n"
        "setlocal\r\n"
        f"cd /d \"{root}\"\r\n"
        "call \"2-停止RemoteCoder-Stop.bat\"\r\n"
    )
}

for path, content in files.items():
    with open(path, "wb") as f:
        # utf-8 for Windows UTF-8 system (codepage 65001)
        f.write(content.encode("utf-8"))
    print(f"Created CRLF UTF-8: {path}")

print("All batch files generated successfully!")
