"""Tools library for RemoteCoder autonomous coding agent.
Provides full filesystem access, precise code editing, search, and PowerShell command execution.
"""
import fnmatch
import logging
import os
import re
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger("RemoteCoder.Tools")

DANGEROUS_COMMAND_PATTERNS = [
    r"\brmdir\s+/s\b",
    r"\bremove-item\s+.*-recurse\b",
    r"\bdel\s+/s\b",
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\bstop-process\b",
    r"\btaskkill\b",
    r"\brestart-computer\b",
    r"\bstop-computer\b",
    r"\bshutdown\b",
]

IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".idea", ".vscode", "dist", "build"}


def resolve_path(path: str, base_dir: str = ".") -> str:
    """Expands environment variables and user home, resolving relative to base_dir."""
    p = os.path.expandvars(os.path.expanduser(str(path).strip()))
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(base_dir, p))
    return p


def classify_action_safety(tool_name: str, args: dict) -> dict:
    """Classifies an action as SAFE or SENSITIVE (requiring human confirmation)."""
    if tool_name == "run_powershell":
        cmd = args.get("command", "").lower()
        for pat in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pat, cmd):
                return {
                    "requires_confirmation": True,
                    "reason": "此命令涉及終止程序、強制刪除或修改系統狀態",
                    "risk_level": "HIGH"
                }
    return {
        "requires_confirmation": False,
        "reason": "操作安全",
        "risk_level": "LOW"
    }


def list_directory(path: str = ".", base_dir: str = ".", max_depth: int = 2) -> dict:
    """List directory contents up to a specified depth."""
    target = resolve_path(path, base_dir)
    if not os.path.exists(target):
        return {"error": f"目錄不存在: {target}"}
    if not os.path.isdir(target):
        return {"error": f"路徑不是目錄: {target}"}

    items = []
    base_depth = target.rstrip(os.sep).count(os.sep)

    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        cur_depth = root.rstrip(os.sep).count(os.sep) - base_depth
        if cur_depth >= max_depth:
            dirs.clear()
            continue

        rel_root = os.path.relpath(root, target)
        for d in dirs:
            rel_d = os.path.normpath(os.path.join(rel_root, d)) if rel_root != "." else d
            items.append({"type": "dir", "path": rel_d})
        for f in files:
            rel_f = os.path.normpath(os.path.join(rel_root, f)) if rel_root != "." else f
            size = 0
            try:
                size = os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
            items.append({"type": "file", "path": rel_f, "size": size})

    return {"base": target, "count": len(items), "items": items[:200]}


def read_file(path: str, base_dir: str = ".", start_line: int = 1, line_count: int = 250) -> dict:
    """Reads a section of a file with line numbers."""
    target = resolve_path(path, base_dir)
    if not os.path.exists(target):
        return {"error": f"檔案不存在: {target}"}
    if not os.path.isfile(target):
        return {"error": f"目標不是檔案: {target}"}

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        s_idx = max(1, start_line) - 1
        e_idx = min(total, s_idx + line_count)

        selected = lines[s_idx:e_idx]
        formatted = "".join(f"{i + s_idx + 1:4d}: {line}" for i, line in enumerate(selected))

        return {
            "path": target,
            "total_lines": total,
            "start_line": start_line,
            "lines_shown": len(selected),
            "content": formatted
        }
    except Exception as e:
        return {"error": f"讀取失敗: {str(e)}"}


def write_file(path: str, content: str, base_dir: str = ".", mode: str = "overwrite") -> dict:
    """Creates or overwrites/appends a file, creating parent directories automatically."""
    target = resolve_path(path, base_dir)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        file_mode = "a" if mode == "append" else "w"
        with open(target, file_mode, encoding="utf-8") as f:
            f.write(content)

        size = os.path.getsize(target)
        return {"success": True, "path": target, "size": size, "mode": mode}
    except Exception as e:
        return {"error": f"寫入失敗: {str(e)}"}


def edit_file_replace(path: str, old_string: str, new_string: str, base_dir: str = ".") -> dict:
    """Replaces a unique block of text in a file."""
    target = resolve_path(path, base_dir)
    if not os.path.exists(target):
        return {"error": f"檔案不存在: {target}"}

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        count = content.count(old_string)
        if count == 0:
            return {"error": "找不到目標替換內容 (old_string)，請先 read_file 確認精確內容"}
        if count > 1:
            return {"error": f"目標內容出現了 {count} 次，不是唯一起點，請提供包含更多前後行的唯一上下文"}

        new_content = content.replace(old_string, new_string, 1)
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {"success": True, "path": target, "replaced": 1}
    except Exception as e:
        return {"error": f"修改失敗: {str(e)}"}


def search_code(query: str, path: str = ".", base_dir: str = ".", max_matches: int = 30) -> dict:
    """Searches for a text pattern across files in the directory."""
    target = resolve_path(path, base_dir)
    matches = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".exe", ".bin", ".mp3", ".wav"}:
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                    for lno, line in enumerate(file, 1):
                        if query.lower() in line.lower():
                            rel_p = os.path.relpath(fp, target)
                            matches.append({"file": rel_p, "line": lno, "content": line.strip()[:150]})
                            if len(matches) >= max_matches:
                                break
            except Exception:
                continue
            if len(matches) >= max_matches:
                break
        if len(matches) >= max_matches:
            break

    return {"query": query, "match_count": len(matches), "matches": matches}


def run_powershell(command: str, base_dir: str = ".", timeout: int = 30) -> dict:
    """Executes a PowerShell command in the target working directory with UTF-8 encoding."""
    utf8_cmd = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$PSDefaultParameterValues['*:Encoding'] = 'utf8'; "
        + command
    )
    target_cwd = resolve_path(".", base_dir)
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", utf8_cmd],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "success": proc.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"error": f"命令執行超時（超過 {timeout} 秒）", "returncode": -1, "success": False}
    except Exception as e:
        return {"error": f"執行失敗: {str(e)}", "returncode": -1, "success": False}


TOOL_DEFINITIONS = [
    {
        "name": "list_directory",
        "description": "探索指定目錄下的檔案與子資料夾列表",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "目錄相對或絕對路徑，預設 '.'"},
                "max_depth": {"type": "INTEGER", "description": "探索深度，預設 2"}
            }
        }
    },
    {
        "name": "read_file",
        "description": "閱讀檔案特定範圍內容，帶有行號",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "檔案路徑"},
                "start_line": {"type": "INTEGER", "description": "起始行號 (從 1 開始)"},
                "line_count": {"type": "INTEGER", "description": "讀取行數 (預設 250 行)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "建立新檔案或覆寫現有檔案，自動建立父資料夾",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "目標檔案路徑"},
                "content": {"type": "STRING", "description": "檔案完整文字內容"},
                "mode": {"type": "STRING", "description": "寫入模式：'overwrite' 或 'append'"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file_replace",
        "description": "精準替換檔案中的某段獨一無二的代碼文字區塊",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "目標檔案路徑"},
                "old_string": {"type": "STRING", "description": "檔案中要被替換的原文字區塊 (必須唯一)"},
                "new_string": {"type": "STRING", "description": "準備換上的新文字區塊"}
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "search_code",
        "description": "在專案代碼中全文搜尋指定關鍵字",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "搜尋關鍵字"},
                "path": {"type": "STRING", "description": "搜尋起點目錄，預設 '.'"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_powershell",
        "description": "在專案工作區執行 PowerShell 命令，用於編譯、建置、測試或檢查",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "PowerShell 命令字串"}
            },
            "required": ["command"]
        }
    }
]
