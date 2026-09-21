"""Task storage and persistence manager for RemoteCoder.
Saves task state, metadata, full execution logs, and conversation messages to local disk.
"""
import json
import os
import shutil
import time
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
TASKS_DIR = os.path.join(OUTPUTS_DIR, "tasks")


class TaskStorage:
    def __init__(self, tasks_dir: str = TASKS_DIR):
        self.tasks_dir = tasks_dir
        os.makedirs(self.tasks_dir, exist_ok=True)

    def _task_dir(self, task_id: str) -> str:
        d = os.path.join(self.tasks_dir, task_id)
        os.makedirs(d, exist_ok=True)
        return d

    def create_task(self, task_id: str, prompt: str, target_dir: str = ".", attachments: Optional[List[dict]] = None) -> dict:
        td = self._task_dir(task_id)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        first_msg = {
            "role": "user",
            "text": prompt,
            "time": time.strftime("%H:%M:%S")
        }
        if attachments:
            first_msg["attachments"] = attachments

        metadata = {
            "id": task_id,
            "prompt": prompt,
            "target_dir": target_dir,
            "status": "running",
            "created_at": now,
            "completed_at": None,
            "summary": "",
            "pending_action": None,
            "events_count": 0,
            "messages": [first_msg]
        }
        with open(os.path.join(td, "task.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        att_desc = f" (附加 {len(attachments)} 個檔案/圖片)" if attachments else ""
        self.append_log(task_id, f"[{now}] 🚀 任務已建立: {prompt}{att_desc}")
        return metadata

    def get_task(self, task_id: str) -> Optional[dict]:
        meta_file = os.path.join(self.tasks_dir, task_id, "task.json")
        if not os.path.exists(meta_file):
            return None
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                task = json.load(f)
                if "messages" not in task:
                    task["messages"] = []
                    if task.get("prompt"):
                        task["messages"].append({"role": "user", "text": task["prompt"], "time": task.get("created_at", "")})
                    if task.get("summary"):
                        task["messages"].append({"role": "assistant", "text": task["summary"], "time": task.get("completed_at", "")})
                return task
        except Exception:
            return None

    def update_task(self, task_id: str, **kwargs) -> Optional[dict]:
        task = self.get_task(task_id)
        if not task:
            return None
        task.update(kwargs)
        meta_file = os.path.join(self.tasks_dir, task_id, "task.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        return task

    def append_message(self, task_id: str, role: str, text: str, attachments: Optional[List[dict]] = None):
        task = self.get_task(task_id)
        if not task:
            return
        if "messages" not in task:
            task["messages"] = []
        msg_obj = {
            "role": role,
            "text": text,
            "time": time.strftime("%H:%M:%S")
        }
        if attachments:
            msg_obj["attachments"] = attachments

        task["messages"].append(msg_obj)
        meta_file = os.path.join(self.tasks_dir, task_id, "task.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    def append_log(self, task_id: str, line: str):
        td = self._task_dir(task_id)
        log_file = os.path.join(td, "execution.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")

    def get_logs(self, task_id: str) -> str:
        log_file = os.path.join(self.tasks_dir, task_id, "execution.log")
        if not os.path.exists(log_file):
            return ""
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def list_tasks(self, limit: int = 50) -> List[dict]:
        if not os.path.exists(self.tasks_dir):
            return []
        tasks = []
        for name in os.listdir(self.tasks_dir):
            meta_path = os.path.join(self.tasks_dir, name, "task.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception:
                    continue
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return tasks[:limit]

    def delete_task(self, task_id: str) -> bool:
        td = os.path.join(self.tasks_dir, task_id)
        if os.path.exists(td):
            try:
                shutil.rmtree(td)
                return True
            except Exception:
                return False
        return False

    def clear_all_tasks(self) -> int:
        count = 0
        if os.path.exists(self.tasks_dir):
            for name in os.listdir(self.tasks_dir):
                p = os.path.join(self.tasks_dir, name)
                if os.path.isdir(p):
                    try:
                        shutil.rmtree(p)
                        count += 1
                    except Exception:
                        pass
        return count


storage = TaskStorage()
