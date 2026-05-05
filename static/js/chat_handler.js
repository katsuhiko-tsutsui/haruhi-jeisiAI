// HARUHI ver.1.31 Chat Handler
// 思考ナビゲーター対応版
// JEISI 2026
// ================================

let userId = sessionStorage.getItem("haruhi_user_id")
          || localStorage.getItem("haruhi_user_id");

if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem("haruhi_user_id", userId);
}

document.addEventListener("DOMContentLoaded", () => {

    const input = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-button");
    const chatMessages = document.getElementById("chat-messages");
    const sessionList = document.getElementById("session-list");
    const newChatBtn = document.getElementById("new-chat-btn");

    // 思考ナビゲーター用カウンター
    let questionCount = 0;

    // =========================
    // メッセージ描画
    // =========================
    function appendMessage(role, text) {
        if (role === "assistant") {
            const wrapper = document.createElement("div");
            wrapper.classList.add("assistant-message");

            const inner = document.createElement("div");
            inner.classList.add("assistant-card");
            inner.innerHTML = text;

            wrapper.appendChild(inner);
            chatMessages.appendChild(wrapper);
        } else if (role === "navigator") {
            // 思考ナビゲーターメッセージ（専用スタイル）
            const wrapper = document.createElement("div");
            wrapper.classList.add("navigator-message");

            const inner = document.createElement("div");
            inner.classList.add("navigator-card");
            inner.innerHTML = text.replace(/\n/g, "<br>");

            wrapper.appendChild(inner);
            chatMessages.appendChild(wrapper);
        } else {
            const div = document.createElement("div");
            div.classList.add("user-message");
            div.innerText = text;
            chatMessages.appendChild(div);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // =========================
    // 思考ナビゲーター呼び出し
    // =========================
    async function fetchNavigatorAdvice() {
        const sessionId = localStorage.getItem("haruhi_session_id");
        if (!sessionId) return;

        try {
            const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
            const res = await fetch("/get_navigator_advice", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                body: JSON.stringify({ session_id: sessionId })
            });

            const data = await res.json();
            if (data.advice) {
                appendMessage("navigator", "🧭 **思考ナビゲーター**\n\n" + data.advice);
            }
        } catch (err) {
            console.error("Navigator error:", err);
        }
    }

    // =========================
    // チャット送信
    // =========================
    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        appendMessage("user", text);
        input.value = "";

        let sessionId = localStorage.getItem("haruhi_session_id");

        try {
            const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
            const res = await fetch("/haruhi_chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId,
                    user_id: userId,
                })
            });

            const data = await res.json();

            if (data.session_id) {
                localStorage.setItem("haruhi_session_id", data.session_id);
            }

            appendMessage("assistant", data.reply);

            // 問いカウントを増やし、3問ごとにナビゲーター自動起動
            questionCount++;
            if (questionCount % 3 === 0) {
                await fetchNavigatorAdvice();
            }

            loadSessions();
        } catch (err) {
            appendMessage("assistant", "⚠ エラーが発生しました。\n" + err);
        }
    }

    // =========================
    // セッション一覧読み込み
    // =========================
    async function loadSessions() {
        const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
        const res = await fetch(`/get_sessions?user_id=${userId}`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
        });
        const data = await res.json();

        sessionList.innerHTML = "";

        data.sessions.forEach(sess => {
            const div = document.createElement("div");
            div.classList.add("session-item");
            div.innerText = sess.title;
            div.dataset.id = sess.session_id;

            div.addEventListener("click", () => {
                questionCount = 0; // セッション切替時にカウントリセット
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

    // =========================
    // 新しいチャット
    // =========================
    newChatBtn.addEventListener("click", async () => {
        try {
            const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
            const res = await fetch("/create_session", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                body: JSON.stringify({ user_id: userId })
            });
            const data = await res.json();

            if (data.session_id) {
                localStorage.setItem("haruhi_session_id", data.session_id);
            }

            chatMessages.innerHTML = "";
            questionCount = 0; // 新チャット時にカウントリセット
            appendMessage("assistant", "こんにちは。今日はどんなことを考えますか？");

            loadSessions();
        } catch (error) {
            appendMessage("assistant", "⚠ 新規チャットの作成に失敗しました。\n" + error);
        }
    });

    // =========================
    // 🧭 手動ナビゲーターボタン
    // =========================
    const navigatorBtn = document.getElementById("navigator-btn");
    if (navigatorBtn) {
        navigatorBtn.addEventListener("click", async () => {
            await fetchNavigatorAdvice();
        });
    }

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

// =========================
// PDGツリー読み込み
// =========================
async function loadPDG() {
    const pdgContainer = document.getElementById("pdg-tree");
    if (!pdgContainer) return; // PDG表示要素がないページでは何もしない

    const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
    const res = await fetch(`/get_pdg_tree`, {
        headers: { "Authorization": `Bearer ${accessToken}` }
    });
    const nodes = await res.json();

    pdgContainer.innerHTML = "<h3>PDG 思考系譜</h3>";

    nodes.forEach(n => {
        const div = document.createElement("div");
        div.style.marginLeft = n.parent ? "30px" : "0px";
        div.innerText = "• " + n.text;
        pdgContainer.appendChild(div);
    });
}

loadPDG();