// RemoteCoder Web UI Controller with SSE Live Streaming & Multi-turn Conversational Tasks

let currentTaskId = null;
let currentEventSource = null;
let pendingFollowupAttachments = [];

const terminalScreen = document.getElementById("terminal-screen");
const autoscrollChk = document.getElementById("autoscroll-chk");
const approvalBanner = document.getElementById("approval-banner");
const approvalReason = document.getElementById("approval-reason");
const displayTaskId = document.getElementById("display-task-id");
const displayTaskPrompt = document.getElementById("display-task-prompt");
const displayTaskStatus = document.getElementById("display-task-status");
const historyList = document.getElementById("history-list");
const chatThread = document.getElementById("chat-thread");
const followupCard = document.getElementById("followup-card");
const followupInput = document.getElementById("followup-input");
const followupBtn = document.getElementById("followup-btn");
const followupAttachmentsElem = document.getElementById("followup-attachments");
const followupFileInput = document.getElementById("followup-file-input");

// 初始化
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadHistory();
  setupEventListeners();
  setupAttachmentHandlers();
  renderWelcome();
});

function renderWelcome() {
  chatThread.innerHTML = `
    <div class="chat-welcome" id="chat-welcome">
      <div class="welcome-icon">⚡</div>
      <h2>RemoteCoder 獨立 AI 工程師</h2>
      <p>隨時在下方輸入聊天問題、交代開發任務，或直接按 Ctrl+V 貼上截圖。大腦將自主規劃、調用工具並即時回覆。</p>
      <div class="quick-chips">
        <button type="button" class="chip" data-text="電腦桌面有沒有 C# 的資料夾？幫我查一下。">🔍 查桌面 C# 資料夾</button>
        <button type="button" class="chip" data-text="請掃描當前專案目錄架構，並整理分析報告。">📂 掃描目錄架構</button>
        <button type="button" class="chip" data-text="你好，請介紹你自己以及你可以幫我做什麼？">💬 日常諮詢問候</button>
      </div>
    </div>
  `;
  bindQuickChips();
}

function bindQuickChips() {
  document.querySelectorAll(".chip").forEach(chip => {
    chip.onclick = () => {
      followupInput.value = chip.getAttribute("data-text");
      followupInput.focus();
    };
  });
}

function startFreshNewChat() {
  clearSessionUI();
  currentTaskId = null;
  displayTaskId.textContent = "無進行中任務";
  displayTaskPrompt.textContent = "請在下方輸入訊息開始新對話，或點選歷史紀錄回放";
  updateStatusBadge("idle", "待命中");
  renderWelcome();
  followupInput.focus();
}

function setupAttachmentHandlers() {
  if (followupFileInput) {
    followupFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(Array.from(e.target.files), pendingFollowupAttachments, followupAttachmentsElem);
        e.target.value = "";
      }
    });
  }

  if (followupInput) {
    setupPasteListener(followupInput, pendingFollowupAttachments, followupAttachmentsElem);
    setupDropListener(followupInput, pendingFollowupAttachments, followupAttachmentsElem);

    // Enter 發送、Shift+Enter 換行
    followupInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        document.getElementById("followup-form").requestSubmit();
      }
    });

    // 文字框高度自適應
    followupInput.addEventListener("input", () => {
      followupInput.style.height = "auto";
      followupInput.style.height = Math.min(followupInput.scrollHeight, 120) + "px";
    });
  }
}

function handleFiles(files, targetArray, containerElem) {
  for (const file of files) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const b64 = e.target.result;
      const isImg = file.type.startsWith("image/");
      const att = {
        name: file.name,
        mime_type: file.type || "application/octet-stream",
        data: b64,
        isImage: isImg
      };
      targetArray.push(att);
      renderAttachments(targetArray, containerElem);
    };
    reader.readAsDataURL(file);
  }
}

function renderAttachments(targetArray, containerElem) {
  if (!containerElem) return;
  containerElem.innerHTML = "";
  targetArray.forEach((att, idx) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";
    if (att.isImage) {
      chip.innerHTML = `
        <img class="attachment-thumb" src="${att.data}" alt="${escapeHtml(att.name)}">
        <span class="attachment-name">${escapeHtml(att.name)}</span>
        <button type="button" class="btn-remove-att" title="移除">✕</button>
      `;
    } else {
      chip.innerHTML = `
        <span>📄</span>
        <span class="attachment-name">${escapeHtml(att.name)}</span>
        <button type="button" class="btn-remove-att" title="移除">✕</button>
      `;
    }
    chip.querySelector(".btn-remove-att").addEventListener("click", () => {
      targetArray.splice(idx, 1);
      renderAttachments(targetArray, containerElem);
    });
    containerElem.appendChild(chip);
  });
}

function setupPasteListener(inputElem, targetArray, containerElem) {
  inputElem.addEventListener("paste", (e) => {
    if (!e.clipboardData || !e.clipboardData.items) return;
    const items = e.clipboardData.items;
    const filesToRead = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        const f = items[i].getAsFile();
        if (f) filesToRead.push(f);
      }
    }
    if (filesToRead.length > 0) {
      e.preventDefault();
      handleFiles(filesToRead, targetArray, containerElem);
    }
  });
}

function setupDropListener(dropZone, targetArray, containerElem) {
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files), targetArray, containerElem);
    }
  });
}

function setupEventListeners() {
  // 統一輸入框表單：發起新對話 或 接續當前任務
  document.getElementById("followup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = followupInput.value.trim();
    const attachments = pendingFollowupAttachments.slice();
    if (!msg && attachments.length === 0) return;

    followupBtn.disabled = true;
    followupInput.value = "";
    followupInput.style.height = "auto";
    pendingFollowupAttachments = [];
    renderAttachments(pendingFollowupAttachments, followupAttachmentsElem);

    // 清除歡迎卡片
    const welcome = document.getElementById("chat-welcome");
    if (welcome) welcome.remove();

    // 情況 1：尚未建立任務 -> 發起全新任務/對話
    if (!currentTaskId) {
      const targetDirInput = document.getElementById("target-dir");
      const targetDir = (targetDirInput ? targetDirInput.value.trim() : "") || ".";
      const promptText = msg || (attachments.length > 0 ? "請分析附帶的圖片/檔案" : "");

      appendChatBubble("user", msg, null, attachments);
      updateStatusBadge("running", "啟動中...");

      try {
        const resp = await fetch("/api/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: promptText,
            target_dir: targetDir,
            attachments: attachments.map(a => ({ name: a.name, mime_type: a.mime_type, data: a.data }))
          })
        });
        const data = await resp.json();
        if (data.ok && data.task_id) {
          currentTaskId = data.task_id;
          displayTaskId.textContent = data.task_id;
          displayTaskPrompt.textContent = promptText;
          connectEventStream(data.task_id, promptText);
          loadHistory();
        } else {
          alert(data.detail || "啟動任務失敗");
          updateStatusBadge("failed", "失敗");
        }
      } catch (err) {
        alert("連線後端伺服器失敗: " + err);
        updateStatusBadge("failed", "連線失敗");
      } finally {
        followupBtn.disabled = false;
        followupInput.focus();
      }
      return;
    }

    // 情況 2：已有進行中任務 -> 接續發話
    appendChatBubble("user", msg, null, attachments);
    updateStatusBadge("running", "思考/執行中");

    try {
      const res = await fetch(`/api/tasks/${currentTaskId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          attachments: attachments.map(a => ({ name: a.name, mime_type: a.mime_type, data: a.data }))
        })
      });
      const data = await res.json();
      if (data.ok) {
        if (!currentEventSource || currentEventSource.readyState === EventSource.CLOSED) {
          connectEventStream(currentTaskId, displayTaskPrompt.textContent);
        }
        loadHistory();
      } else {
        alert(data.detail || "發送訊息失敗");
      }
    } catch (err) {
      alert("連線伺服器失敗: " + err);
    } finally {
      followupBtn.disabled = false;
      followupInput.focus();
    }
  });

  // 開啟全新對話/任務按鈕 (頂部與側邊欄)
  const newBtn1 = document.getElementById("new-task-btn");
  const newBtn2 = document.getElementById("sidebar-new-task-btn");
  if (newBtn1) newBtn1.addEventListener("click", startFreshNewChat);
  if (newBtn2) newBtn2.addEventListener("click", startFreshNewChat);

  // 清空全部歷史
  document.getElementById("clear-all-btn").addEventListener("click", async () => {
    if (!confirm("確定要清空所有任務與對話歷史紀錄嗎？（硬碟上的 task 目錄將會被刪除）")) return;
    try {
      await fetch("/api/tasks", { method: "DELETE" });
      startFreshNewChat();
      loadHistory();
    } catch (err) {
      alert("清空失敗: " + err);
    }
  });

  // 清空終端機
  document.getElementById("clear-terminal-btn").addEventListener("click", clearTerminal);

  // 收合/展開終端機
  const toggleTermBtn = document.getElementById("toggle-terminal-btn");
  if (toggleTermBtn) {
    toggleTermBtn.addEventListener("click", () => {
      const termCard = document.getElementById("terminal-card");
      const split = document.getElementById("workspace-split");
      if (termCard) {
        termCard.classList.toggle("collapsed");
        if (split) split.classList.toggle("terminal-collapsed");
        toggleTermBtn.textContent = termCard.classList.contains("collapsed") ? "展開 ▴" : "收合日誌 ▾";
      }
    });
  }

  // 重新整理歷史列表
  document.getElementById("refresh-history-btn").addEventListener("click", loadHistory);

  // 審批按鈕
  document.getElementById("btn-approve").addEventListener("click", async () => {
    if (!currentTaskId) return;
    try {
      await fetch(`/api/tasks/${currentTaskId}/approve`, { method: "POST" });
      approvalBanner.style.display = "none";
    } catch (e) {
      console.error(e);
    }
  });

  document.getElementById("btn-reject").addEventListener("click", async () => {
    if (!currentTaskId) return;
    try {
      await fetch(`/api/tasks/${currentTaskId}/reject`, { method: "POST" });
      approvalBanner.style.display = "none";
    } catch (e) {
      console.error(e);
    }
  });
}

async function checkHealth() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    if (data.status === "ok") {
      document.getElementById("conn-badge").className = "badge badge-online";
      document.getElementById("conn-badge").textContent = "● 伺服器在線 (HTTP 8080)";
      document.getElementById("local-ip-badge").textContent = `IP: ${data.local_ip}:8080`;
    }
  } catch (err) {
    document.getElementById("conn-badge").className = "badge badge-failed";
    document.getElementById("conn-badge").textContent = "● 伺服器離線";
  }
}

async function loadHistory() {
  try {
    const res = await fetch("/api/tasks");
    const tasks = await res.json();
    if (!Array.isArray(tasks) || tasks.length === 0) {
      historyList.innerHTML = `<div class="empty-state">尚無執行任務</div>`;
      return;
    }

    historyList.innerHTML = tasks.map(t => {
      const statusClass = t.status === "completed" ? "badge-completed" :
                          t.status === "running" ? "badge-running" :
                          t.status === "waiting_approval" ? "badge-waiting" : "badge-failed";
      const statusLabel = t.status === "completed" ? "完成" :
                          t.status === "running" ? "運行中" :
                          t.status === "waiting_approval" ? "待授權" : "失敗";
      const shortId = t.id.split('-').slice(1).join('-');
      return `
        <div class="history-item ${t.id === currentTaskId ? 'active' : ''}" onclick="selectHistoryTask('${t.id}', '${escapeHtml(t.prompt)}')">
          <div class="history-item-top">
            <span>${shortId}</span>
            <div class="history-item-right">
              <span class="badge ${statusClass}" style="font-size: 10px; padding: 1px 6px;">${statusLabel}</span>
              <button class="btn-delete-task" title="刪除此紀錄" onclick="deleteSingleTask(event, '${t.id}')">✕</button>
            </div>
          </div>
          <div class="history-item-prompt">${escapeHtml(t.prompt)}</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("載入歷史失敗:", err);
  }
}

async function deleteSingleTask(event, taskId) {
  event.stopPropagation();
  if (!confirm(`確定要刪除這筆紀錄 (${taskId}) 嗎？`)) return;

  try {
    const res = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.ok) {
      if (currentTaskId === taskId) {
        clearSessionUI();
        currentTaskId = null;
        showFollowupBar(false);
      }
      loadHistory();
    }
  } catch (err) {
    alert("刪除失敗: " + err);
  }
}

async function selectHistoryTask(taskId, prompt) {
  clearSessionUI();
  const mainContent = document.querySelector(".main-content");
  if (mainContent) {
    mainContent.scrollIntoView({ behavior: "smooth" });
  }

  currentTaskId = taskId;
  displayTaskId.textContent = taskId;
  displayTaskPrompt.textContent = prompt || taskId;
  approvalBanner.style.display = "none";
  showFollowupBar(true);

  try {
    const res = await fetch(`/api/tasks/${taskId}`);
    const data = await res.json();
    const task = data.task;
    const logs = data.logs;

    if (logs) {
      appendRawLog(logs);
    }

    // 渲染對話泡泡歷史
    if (task && Array.isArray(task.messages)) {
      chatThread.innerHTML = "";
      task.messages.forEach(m => {
        appendChatBubble(m.role, m.text, m.time, m.attachments);
      });
    }

    if (task && (task.status === "completed" || task.status === "failed")) {
      const isOk = task.status === "completed";
      updateStatusBadge(task.status, isOk ? "已完成" : "失敗");
      loadHistory();
      return;
    }
  } catch (err) {
    console.error("載入任務詳情異常:", err);
  }

  // 任務仍在進行中，連線即時串流
  connectEventStream(taskId, prompt);
  loadHistory();
}

function connectEventStream(taskId, prompt) {
  if (currentEventSource) {
    currentEventSource.close();
  }

  currentTaskId = taskId;
  displayTaskId.textContent = taskId;
  displayTaskPrompt.textContent = prompt || taskId;
  updateStatusBadge("running", "運行中");
  approvalBanner.style.display = "none";
  showFollowupBar(true);

  appendTerminalLine(`[CONNECT] 正在連線任務即時事件串流 (SSE)...`, "term-welcome");

  currentEventSource = new EventSource(`/api/tasks/${taskId}/events`);

  // 既有歷史日誌追趕
  currentEventSource.addEventListener("catchup", (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.logs) {
        appendRawLog(d.logs);
      }
    } catch (err) {
      console.error(err);
    }
  });

  // 使用者接續發話事件
  currentEventSource.addEventListener("user_message", (e) => {
    try {
      const d = JSON.parse(e.data);
      const lastMsg = chatThread.lastElementChild;
      const lastText = lastMsg ? lastMsg.querySelector(".msg-text")?.textContent : null;
      if (!lastMsg || lastText !== d.text) {
        appendChatBubble("user", d.text, null, d.attachments);
      }
    } catch (err) {
      console.error(err);
    }
  });

  // 大腦回答 / 總結事件
  currentEventSource.addEventListener("reply", (e) => {
    try {
      const text = typeof e.data === "string" && e.data.startsWith("{") ? JSON.parse(e.data) : e.data;
      appendChatBubble("assistant", text);
    } catch (err) {
      appendChatBubble("assistant", e.data);
    }
  });

  // 大腦思考
  currentEventSource.addEventListener("thought", (e) => {
    try {
      const text = JSON.parse(e.data);
      appendTerminalLine(`🧠 大腦分析思考:\n${text}`, "term-thought");
    } catch (err) {
      appendTerminalLine(`🧠 大腦分析: ${e.data}`, "term-thought");
    }
  });

  // 工具調用
  currentEventSource.addEventListener("tool_call", (e) => {
    try {
      const d = JSON.parse(e.data);
      appendTerminalLine(`🔧 [調用工具] ${d.tool}(${JSON.stringify(d.args)})`, "term-tool-call");
    } catch (err) {
      appendTerminalLine(`🔧 [調用工具] ${e.data}`, "term-tool-call");
    }
  });

  // 工具回傳結果
  currentEventSource.addEventListener("tool_result", (e) => {
    try {
      const d = JSON.parse(e.data);
      const resStr = JSON.stringify(d.result, null, 2);
      appendTerminalLine(`⬅️ [執行結果] ${d.tool}:\n${resStr}`, "term-tool-result");
    } catch (err) {
      appendTerminalLine(`⬅️ [執行結果] ${e.data}`, "term-tool-result");
    }
  });

  // 敏感操作需要審批
  currentEventSource.addEventListener("confirmation_required", (e) => {
    try {
      const d = JSON.parse(e.data);
      approvalReason.textContent = d.reason || `即將執行操作: ${d.tool}`;
      approvalBanner.style.display = "flex";
      updateStatusBadge("waiting_approval", "等待授權");
      appendTerminalLine(`⚠️ [安全攔截] ${d.reason}，等待使用者確認...`, "term-warning");
      approvalBanner.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      console.error(err);
    }
  });

  // 一般終端輸出
  currentEventSource.addEventListener("output", (e) => {
    appendTerminalLine(e.data, "term-line");
  });

  // 狀態變更 (完成/失敗)
  currentEventSource.addEventListener("status", (e) => {
    try {
      const d = JSON.parse(e.data);
      const status = d.status;
      if (status === "completed") {
        updateStatusBadge("completed", "已完成");
        appendTerminalLine(`\n✨ 任務圓滿完成！`, "term-success");
        chatThread.scrollTop = chatThread.scrollHeight;
        currentEventSource.close();
      } else if (status === "failed") {
        updateStatusBadge("failed", "失敗");
        appendTerminalLine(`\n❌ 任務未能完全達成: ${d.summary || ""}`, "term-error");
        currentEventSource.close();
      } else if (status === "running") {
        updateStatusBadge("running", "運行中");
      }
      loadHistory();
    } catch (err) {
      console.error(err);
    }
  });

  // 錯誤處理
  currentEventSource.addEventListener("error", (e) => {
    if (e.data) {
      appendTerminalLine(`[ERROR] ${e.data}`, "term-error");
    }
  });
}

function appendChatBubble(role, text, timeStr, attachments) {
  if (!text && (!attachments || attachments.length === 0)) return;
  const div = document.createElement("div");
  const isUser = (role === "user");
  div.className = `chat-msg ${isUser ? 'msg-user' : 'msg-assistant'}`;

  const time = timeStr || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const author = isUser ? "👤 使用者" : "🤖 RemoteCoder 助理";

  let attHtml = "";
  if (attachments && attachments.length > 0) {
    attHtml = `<div class="msg-attachments">` + attachments.map(att => {
      const src = att.url || att.data;
      const isImg = (att.mime_type && att.mime_type.startsWith("image/")) || att.isImage;
      if (isImg) {
        return `<a href="${src}" target="_blank" title="點擊放大圖片"><img class="chat-thumb" src="${src}" alt="${escapeHtml(att.name)}"></a>`;
      } else {
        return `<a class="chat-file-badge" href="${src}" target="_blank" download="${escapeHtml(att.name)}">📄 ${escapeHtml(att.name)}</a>`;
      }
    }).join("") + `</div>`;
  }

  div.innerHTML = `
    <div class="msg-meta">
      <strong>${author}</strong>
      <span>${time}</span>
    </div>
    ${attHtml}
    ${text ? `<div class="msg-text">${escapeHtml(text)}</div>` : ''}
  `;
  chatThread.appendChild(div);
  chatThread.scrollTop = chatThread.scrollHeight;
}

function showFollowupBar(show) {
  followupCard.style.display = show ? "block" : "none";
}

function updateStatusBadge(status, label) {
  const badgeMap = {
    running: "badge-running",
    waiting_approval: "badge-waiting",
    completed: "badge-completed",
    failed: "badge-failed",
    idle: "badge-idle"
  };
  displayTaskStatus.className = `badge ${badgeMap[status] || "badge-idle"}`;
  displayTaskStatus.textContent = label;
}

function appendTerminalLine(text, className = "term-line") {
  const div = document.createElement("div");
  div.className = className;
  div.textContent = text;
  terminalScreen.appendChild(div);
  if (autoscrollChk.checked) {
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  }
}

function appendRawLog(rawLogs) {
  const div = document.createElement("div");
  div.className = "term-line term-subtle";
  div.textContent = rawLogs;
  terminalScreen.appendChild(div);
  if (autoscrollChk.checked) {
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  }
}

function clearTerminal() {
  terminalScreen.innerHTML = "";
}

function clearSessionUI() {
  clearTerminal();
  chatThread.innerHTML = "";
  approvalBanner.style.display = "none";
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
}
