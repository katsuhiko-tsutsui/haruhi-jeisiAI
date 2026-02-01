// ================================
// HARUHI ver.1.20 Chat Handler (GPT風UI対応版)
// JEISI 2025
// ================================

document.addEventListener("DOMContentLoaded", () => {

    const input = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-button");
    const chatMessages = document.getElementById("chat-messages");
    const modeSelect = document.getElementById("thinking-mode");

    const sessionList = document.getElementById("session-list");
    const newChatBtn = document.getElementById("new-chat-btn");

    // =========================
    // メッセージ描画（GPT風）
    // =========================
    function appendMessage(role, text) {
        if (role === "assistant") {
            // HARUHI：画面中央のカード表示
            const wrapper = document.createElement("div");
            wrapper.classList.add("assistant-message");

            const inner = document.createElement("div");
            inner.classList.add("assistant-card");
            inner.innerHTML = text;

            wrapper.appendChild(inner);
            chatMessages.appendChild(wrapper);
        } else {
            // user：右寄せバブル
            const div = document.createElement("div");
            div.classList.add("user-message");
            div.innerText = text;
            chatMessages.appendChild(div);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // =========================
    // チャット送信
    // =========================
    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        // 自分の発話を先に表示
        appendMessage("user", text);
        input.value = "";

        const mode = modeSelect ? modeSelect.value : "reflective";
        let sessionId = localStorage.getItem("haruhi_session_id");

        try {
            const res = await fetch("/haruhi_chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId,
                    thinking_mode: mode
                })
            });

            const data = await res.json();

            // 新セッションIDを保存
            if (data.session_id) {
                localStorage.setItem("haruhi_session_id", data.session_id);
            }

            // HARUHIの返答
            appendMessage("assistant", data.reply);

            // セッション一覧更新
            loadSessions();
        } catch (err) {
            appendMessage("assistant", "⚠ エラーが発生しました。\n" + err);
        }
    }

    // =========================
    // セッション一覧読み込み
    // =========================
    async function loadSessions() {
        const res = await fetch("/get_sessions");
        const data = await res.json();

        sessionList.innerHTML = "";

        data.sessions.forEach(sess => {
            const div = document.createElement("div");
            div.classList.add("session-item");
            div.innerText = sess.title;
            div.dataset.id = sess.session_id;

            div.addEventListener("click", () => {
                selectSession(sess.session_id);
            });

            sessionList.appendChild(div);
        });
    }

    // =========================
    // セッション切替
    // =========================
    async function selectSession(id) {
        localStorage.setItem("haruhi_session_id", id);

        const res = await fetch(`/get_session_messages/${id}`);
        const data = await res.json();

        chatMessages.innerHTML = "";

        data.messages.forEach(m => {
            appendMessage(m.role, m.content);
        });
    }

    // ==========================================
    // 新しいチャット（New Chat）
    // ==========================================
    newChatBtn.addEventListener("click", async () => {
        try {
            // （1）サーバーに新セッションを作成
            const res = await fetch("/create_session", {
                method: "POST"
            });

            const data = await res.json();

            // （2）session_id を保存
            if (data.session_id) {
                localStorage.setItem("haruhi_session_id", data.session_id);
            }

            // （3）メッセージ欄をクリア
            chatMessages.innerHTML = "";

            // （4）セッション一覧更新
            loadSessions();
        } catch (error) {
            appendMessage("assistant", "⚠ 新規チャットの作成に失敗しました。\n" + error);
        }
    });

    // =========================
    // イベント
    // =========================
    if (sendBtn) {
        sendBtn.addEventListener("click", sendMessage);
    }

    if (input) {
        input.addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // =========================
    // 初期化
    // =========================
    loadSessions();
});
