"""Autonomous Coding & Conversational Engine for RemoteCoder.
Executes an iterative tool-use loop with Gemini, supporting live SSE event publishing,
multi-turn interactive conversations, self-reflection, automatic error correction,
and human-in-the-loop approvals.
"""
import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Dict, Any, List, Optional

from .tools import (
    list_directory,
    read_file,
    write_file,
    edit_file_replace,
    search_code,
    run_powershell,
    classify_action_safety,
    TOOL_DEFINITIONS
)
from .storage import storage

logger = logging.getLogger("RemoteCoder.Engine")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")


def load_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.join(OUTPUTS_DIR, "gemini_api_key.txt")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


SYSTEM_INSTRUCTION = """你是一位全自主遠端軟體工程專家與智慧程式助手 (RemoteCoder)。
你的任務是接收使用者的自然語言需求，在指定的工作目錄中獨立完成專案開發、功能編寫、代碼修改或問題排查。
當使用者與你進行一般對話、諮詢、詢問主機現況或探討技術架構時，請親切有禮地以繁體中文直接回答與互動；
當使用者交代具體的操作任務或編程指令時，請自主規劃並調用本機工具完成開發與驗證。

【工作原則】
1. 靈活互動：如果使用者的輸入是一般對話、問候或問題諮詢，直接以繁體中文清楚回答，不需要強行調用工具；如果有具體操作需求，再調用工具進行作業。
2. 探索先行：調用工具時，先以 list_directory 或 search_code 了解工作區檔案架構，再進行代碼讀取或修改。
3. 精準編輯：優先使用 edit_file_replace 精準修改代碼；若為全新模組或腳本，使用 write_file 建立。
4. 嚴謹驗證：編寫或修改完成後，務必使用 run_powershell 執行語法檢查、建置或單元測試，確保功能真正運作正常。
5. 自我修復：如果測試失敗或回傳錯誤代碼，主動閱讀錯誤訊息並修改代碼，直到驗證通過為止。
6. 親切回報：每次操作完成或回答時，請以清晰專業的繁體中文為使用者條理分明地總結回覆。
"""


def _save_attachments(task_id: str, attachments: Optional[list]) -> List[dict]:
    """Save base64 attachments to outputs/tasks/{task_id}/uploads/ and return metadata list."""
    if not attachments:
        return []
    import base64
    upload_dir = os.path.join(OUTPUTS_DIR, "tasks", task_id, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    saved_meta = []
    for i, att in enumerate(attachments):
        name = att.get("name", f"upload_{int(time.time())}_{i}.png")
        mime = att.get("mime_type", "image/png")
        b64_data = att.get("data", "")
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]

        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ") or f"file_{i}.bin"
        file_path = os.path.join(upload_dir, safe_name)
        try:
            file_bytes = base64.b64decode(b64_data)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            url = f"/outputs/tasks/{task_id}/uploads/{safe_name}"
            saved_meta.append({
                "name": safe_name,
                "mime_type": mime,
                "url": url,
                "size": len(file_bytes),
                "data": b64_data
            })
        except Exception as e:
            logger.error("儲存附件失敗: %s", e)
    return saved_meta


def _build_attachment_parts(saved_meta: List[dict]) -> List[dict]:
    import base64
    parts = []
    for att in saved_meta:
        mime = att.get("mime_type", "")
        if mime.startswith("image/") or mime == "application/pdf":
            parts.append({
                "inlineData": {
                    "mimeType": mime or "image/png",
                    "data": att["data"]
                }
            })
        else:
            try:
                text_content = base64.b64decode(att["data"]).decode("utf-8", errors="replace")
                parts.append({
                    "text": f"【附加檔案內容: {att['name']} ({mime})】\n```\n{text_content}\n```"
                })
            except Exception:
                parts.append({
                    "inlineData": {
                        "mimeType": mime or "application/octet-stream",
                        "data": att["data"]
                    }
                })
    return parts


class CodingEngine:
    def __init__(self):
        self.api_key = load_api_key()
        self._event_queues: Dict[str, List[asyncio.Queue]] = {}
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._approval_verdict: Dict[str, bool] = {}
        # 會話上下文快取：task_id -> {"history": list, "target_dir": str}
        self._sessions: Dict[str, dict] = {}

    def get_event_queue(self, task_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if task_id not in self._event_queues:
            self._event_queues[task_id] = []
        self._event_queues[task_id].append(q)
        return q

    def remove_event_queue(self, task_id: str, q: asyncio.Queue):
        if task_id in self._event_queues:
            try:
                self._event_queues[task_id].remove(q)
            except ValueError:
                pass

    async def emit_event(self, task_id: str, event_type: str, data: Any):
        payload = {
            "type": event_type,
            "data": data,
            "time": time.strftime("%H:%M:%S")
        }
        # 寫入本機硬碟 log
        line = f"[{payload['time']}] [{event_type.upper()}] "
        if isinstance(data, dict):
            line += json.dumps(data, ensure_ascii=False)
        else:
            line += str(data)
        storage.append_log(task_id, line)

        # 廣播至所有監聽該任務的 SSE 隊列
        queues = self._event_queues.get(task_id, [])
        for q in list(queues):
            try:
                await q.put(payload)
            except Exception:
                pass

    def approve_action(self, task_id: str):
        self._approval_verdict[task_id] = True
        if task_id in self._approval_events:
            self._approval_events[task_id].set()

    def reject_action(self, task_id: str):
        self._approval_verdict[task_id] = False
        if task_id in self._approval_events:
            self._approval_events[task_id].set()

    async def run_task(self, task_id: str, prompt: str, target_dir: str = ".", attachments: Optional[list] = None):
        """Start a new autonomous task or conversation."""
        saved_meta = _save_attachments(task_id, attachments)
        storage_meta = [{k: v for k, v in m.items() if k != "data"} for m in saved_meta]

        logger.info("啟動任務 [%s]: %s (工作目錄: %s, 附件: %d)", task_id, prompt, target_dir, len(saved_meta))
        storage.create_task(task_id, prompt, target_dir, attachments=storage_meta)
        await self.emit_event(task_id, "status", {"status": "running", "prompt": prompt})

        if not self.api_key:
            err = "未配置 GEMINI_API_KEY，請在 outputs/gemini_api_key.txt 填入 API Key"
            storage.update_task(task_id, status="failed", summary=err)
            storage.append_message(task_id, "assistant", err)
            await self.emit_event(task_id, "error", err)
            await self.emit_event(task_id, "status", {"status": "failed", "summary": err})
            return

        parts = _build_attachment_parts(saved_meta)

        text_content = (
            f"【任務或對話內容】\n{prompt}\n\n"
            f"【工作區目錄】\n{target_dir}\n\n"
        )
        if saved_meta:
            text_content += f"【使用者附加了 {len(saved_meta)} 個圖片/檔案】: {', '.join(m['name'] for m in saved_meta)}\n\n"
        text_content += "請評估：若包含圖片/文件，請進行多模態分析與解讀；若為一般諮詢請直接以繁體中文回答；若涉及檔案操作或代碼指令，請自主規劃調用工具完成開發與驗證。"

        parts.append({"text": text_content})

        chat_history = [
            {
                "role": "user",
                "parts": parts
            }
        ]
        self._sessions[task_id] = {"history": chat_history, "target_dir": target_dir}
        await self._run_loop(task_id, chat_history, target_dir)

    async def continue_task(self, task_id: str, user_message: str, attachments: Optional[list] = None):
        """Continue conversation in an existing task session."""
        saved_meta = _save_attachments(task_id, attachments)
        storage_meta = [{k: v for k, v in m.items() if k != "data"} for m in saved_meta]

        logger.info("接續任務 [%s] 對話: %s (附件: %d)", task_id, user_message, len(saved_meta))
        storage.append_message(task_id, "user", user_message, attachments=storage_meta)
        storage.update_task(task_id, status="running")
        await self.emit_event(task_id, "status", {"status": "running"})
        await self.emit_event(task_id, "user_message", {"text": user_message, "attachments": storage_meta})

        if task_id in self._sessions:
            session = self._sessions[task_id]
            chat_history = session["history"]
            target_dir = session["target_dir"]
        else:
            task = storage.get_task(task_id) or {}
            target_dir = task.get("target_dir", ".")
            chat_history = []
            for msg in task.get("messages", []):
                role = "user" if msg.get("role") == "user" else "model"
                chat_history.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
            self._sessions[task_id] = {"history": chat_history, "target_dir": target_dir}

        parts = _build_attachment_parts(saved_meta)
        parts.append({"text": user_message})

        chat_history.append({
            "role": "user",
            "parts": parts
        })

        await self._run_loop(task_id, chat_history, target_dir)

    async def _run_loop(self, task_id: str, chat_history: list, target_dir: str):
        """Core multi-turn execution loop."""
        tools_decl = [{"function_declarations": TOOL_DEFINITIONS}]
        max_turns = 15

        for turn in range(max_turns):
            await self.emit_event(task_id, "turn", {"turn": turn + 1, "max_turns": max_turns})

            # 呼叫 Gemini
            gemini_resp = await self._call_gemini(chat_history, tools_decl)
            if not gemini_resp:
                err = "Gemini 連線中斷或無回應"
                await self.emit_event(task_id, "error", err)
                storage.update_task(task_id, status="failed", summary=err)
                storage.append_message(task_id, "assistant", err)
                await self.emit_event(task_id, "status", {"status": "failed", "summary": err})
                return

            candidates = gemini_resp.get("candidates", [])
            if not candidates:
                err = "模型無回傳候選內容"
                await self.emit_event(task_id, "error", err)
                storage.update_task(task_id, status="failed", summary=err)
                storage.append_message(task_id, "assistant", err)
                await self.emit_event(task_id, "status", {"status": "failed", "summary": err})
                return

            msg = candidates[0].get("content", {})
            parts = msg.get("parts", [])

            # 提取文字與思考
            text_blocks = []
            func_calls = []
            for p in parts:
                if "text" in p and p["text"].strip():
                    text_blocks.append(p["text"].strip())
                if "functionCall" in p:
                    func_calls.append(p["functionCall"])

            if text_blocks:
                full_text = "\n\n".join(text_blocks)
                await self.emit_event(task_id, "thought", full_text)

            # 將模型的回應加入歷史
            chat_history.append({"role": "model", "parts": parts})

            # 如果沒有調用任何工具，表示回答或總結已完成
            if not func_calls:
                summary = text_blocks[-1] if text_blocks else "任務已執行完成。"
                storage.append_message(task_id, "assistant", summary)
                storage.update_task(task_id, status="completed", summary=summary, completed_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                await self.emit_event(task_id, "reply", summary)
                await self.emit_event(task_id, "status", {"status": "completed", "summary": summary})
                logger.info("任務 [%s] 圓滿完成/已回覆！", task_id)
                return

            # 依序執行工具調用
            tool_responses = []
            for fc in func_calls:
                func_name = fc.get("name")
                func_args = fc.get("args", {})

                # 補上 base_dir
                if "base_dir" not in func_args and func_name in ["list_directory", "read_file", "write_file", "edit_file_replace", "search_code", "run_powershell"]:
                    func_args["base_dir"] = target_dir

                # 安全檢測與審批暫停
                safety = classify_action_safety(func_name, func_args)
                if safety["requires_confirmation"]:
                    await self.emit_event(task_id, "confirmation_required", {
                        "tool": func_name,
                        "args": func_args,
                        "reason": safety["reason"]
                    })
                    storage.update_task(task_id, status="waiting_approval", pending_action={"tool": func_name, "args": func_args, "reason": safety["reason"]})

                    # 暫停等待審批
                    evt = asyncio.Event()
                    self._approval_events[task_id] = evt
                    await evt.wait()
                    verdict = self._approval_verdict.get(task_id, False)
                    self._approval_events.pop(task_id, None)

                    if not verdict:
                        await self.emit_event(task_id, "output", f"🚫 使用者已取消此操作: {func_name}")
                        storage.update_task(task_id, status="running", pending_action=None)
                        tool_responses.append({
                            "functionResponse": {
                                "name": func_name,
                                "response": {"error": "使用者取消了此操作"}
                            }
                        })
                        continue
                    else:
                        await self.emit_event(task_id, "output", f"✅ 使用者已授權執行: {func_name}")
                        storage.update_task(task_id, status="running", pending_action=None)

                # 執行本機工具
                await self.emit_event(task_id, "tool_call", {"tool": func_name, "args": func_args})
                tool_res = await asyncio.to_thread(self._execute_tool, func_name, func_args)
                await self.emit_event(task_id, "tool_result", {"tool": func_name, "result": tool_res})

                resp_obj = {"result": tool_res} if not isinstance(tool_res, dict) else tool_res
                fr = {
                    "functionResponse": {
                        "name": func_name,
                        "response": resp_obj
                    }
                }
                if "id" in fc:
                    fr["functionResponse"]["id"] = fc["id"]
                tool_responses.append(fr)

            # 將工具執行結果作為 user 角色推入對話歷史
            chat_history.append({
                "role": "user",
                "parts": tool_responses
            })

        # 超過最大輪數
        summary = "任務已達到最大執行輪數上限，已中斷以保障系統穩定。"
        storage.append_message(task_id, "assistant", summary)
        storage.update_task(task_id, status="failed", summary=summary, completed_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        await self.emit_event(task_id, "reply", summary)
        await self.emit_event(task_id, "status", {"status": "failed", "summary": summary})

    def _execute_tool(self, name: str, args: dict) -> dict:
        mapping = {
            "list_directory": list_directory,
            "read_file": read_file,
            "write_file": write_file,
            "edit_file_replace": edit_file_replace,
            "search_code": search_code,
            "run_powershell": run_powershell
        }
        fn = mapping.get(name)
        if not fn:
            return {"error": f"找不到指定工具: {name}"}
        try:
            return fn(**args)
        except Exception as e:
            return {"error": f"工具執行例外: {str(e)}"}

    async def _call_gemini(self, contents: list, tools: list) -> Optional[dict]:
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "tools": tools,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        models = ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-flash-latest"]
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
            try:
                res = await asyncio.to_thread(self._http_post, url, payload, 30)
                if res and "candidates" in res:
                    return res
            except Exception as e:
                logger.warning("模型 %s 調用失敗: %s", m, e)
                await asyncio.sleep(0.5)

        return None

    def _http_post(self, url: str, data: dict, timeout: int = 30) -> dict:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


engine = CodingEngine()
