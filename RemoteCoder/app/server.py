"""FastAPI server for RemoteCoder standalone autonomous coding engine.
Provides REST API, Web UI, and Server-Sent Events (SSE) live typewriter streaming.
"""
import asyncio
import json
import logging
import os
import socket
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

if sys.platform == "win32":
    try:
        if sys.stdout is None:
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
            sys.stdout = open(os.path.join(OUTPUTS_DIR, "server.log"), "a", encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr is None:
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
            sys.stderr = open(os.path.join(OUTPUTS_DIR, "server_err.log"), "a", encoding="utf-8")
        else:
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import time
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import engine
from .storage import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RemoteCoder.Server")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

app = FastAPI(title="RemoteCoder", description="Standalone Autonomous Coding Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateTaskRequest(BaseModel):
    prompt: str
    target_dir: Optional[str] = "."
    attachments: Optional[list] = None


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": "RemoteCoder",
        "version": "1.0.0",
        "local_ip": get_local_ip(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest):
    prompt = req.prompt.strip()
    if not prompt and not req.attachments:
        raise HTTPException(status_code=400, detail="任務指示或附件不可為空")

    target_dir = req.target_dir.strip() if req.target_dir else "."
    task_id = f"task-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

    # 背景非同步啟動任務大腦循環
    asyncio.create_task(engine.run_task(task_id, prompt, target_dir, attachments=req.attachments))

    return {
        "ok": True,
        "task_id": task_id,
        "prompt": prompt,
        "target_dir": target_dir,
        "status": "running"
    }


class FollowUpRequest(BaseModel):
    message: str
    attachments: Optional[list] = None


@app.post("/api/tasks/{task_id}/messages")
async def send_followup_message(task_id: str, req: FollowUpRequest):
    msg = req.message.strip()
    if not msg and not req.attachments:
        raise HTTPException(status_code=400, detail="訊息或附件不可為空")
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")

    asyncio.create_task(engine.continue_task(task_id, msg, attachments=req.attachments))
    return {"ok": True, "task_id": task_id, "status": "running"}


@app.get("/api/tasks")
async def list_tasks(limit: int = 30):
    return storage.list_tasks(limit=limit)


@app.delete("/api/tasks")
async def clear_all_tasks():
    count = storage.clear_all_tasks()
    return {"ok": True, "cleared_count": count}


@app.get("/api/tasks/{task_id}")
async def get_task_details(task_id: str):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="找不到指定任務")
    logs = storage.get_logs(task_id)
    return {"task": task, "logs": logs}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    success = storage.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="找不到指定任務或刪除失敗")
    return {"ok": True, "deleted": task_id}


@app.get("/api/tasks/{task_id}/events")
async def stream_task_events(task_id: str, request: Request):
    """Server-Sent Events (SSE) endpoint providing live terminal typewriter stream."""
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="找不到指定任務")

    async def event_generator():
        # 1. 先推播既有日誌作為歷史追趕 (Catch-up)
        logs = storage.get_logs(task_id)
        if logs:
            yield f"event: catchup\ndata: {json.dumps({'logs': logs}, ensure_ascii=False)}\n\n"

        # 若任務已結束，推播結束狀態並退出
        cur_task = storage.get_task(task_id)
        if cur_task and cur_task.get("status") in ["completed", "failed"]:
            yield f"event: status\ndata: {json.dumps(cur_task, ensure_ascii=False)}\n\n"
            return

        # 2. 監聽即時事件隊列
        q = engine.get_event_queue(task_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    evt_type = event.get("type", "message")
                    data_str = json.dumps(event.get("data", {}), ensure_ascii=False)
                    yield f"event: {evt_type}\ndata: {data_str}\n\n"

                    # 若任務完成或失敗，結束串流
                    if evt_type == "status" and event.get("data", {}).get("status") in ["completed", "failed"]:
                        break
                except asyncio.TimeoutError:
                    # 發送保活心跳註解
                    yield ": ping\n\n"
        finally:
            engine.remove_event_queue(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/tasks/{task_id}/approve")
async def approve_task_action(task_id: str):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")
    engine.approve_action(task_id)
    return {"ok": True, "task_id": task_id, "action": "approved"}


@app.post("/api/tasks/{task_id}/reject")
async def reject_task_action(task_id: str):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")
    engine.reject_action(task_id)
    return {"ok": True, "task_id": task_id, "action": "rejected"}


# 掛載 Web 靜態資源與任務產出/附件目錄
if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")


@app.get("/")
async def serve_index():
    index_file = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"app": "RemoteCoder", "status": "web_ui_loading"})


def main():
    port = int(os.getenv("PORT", "8080"))
    local_ip = get_local_ip()
    print("=" * 60)
    print(" [RemoteCoder] Standalone Autonomous Coding Server Started")
    print(f" Local URL: http://localhost:{port}")
    print(f" LAN / Phone: http://{local_ip}:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
