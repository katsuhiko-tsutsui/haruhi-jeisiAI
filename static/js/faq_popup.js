let sakuraVisible = false;

// --- 初期メッセージ用フラグ ---
let sakuraInitialAdded = false;

// FAQウィンドウ開閉
function toggleSakuraFAQ() {
    sakuraVisible = !sakuraVisible;

    const win = document.getElementById("sakura-faq-window");

    if (sakuraVisible) {
        win.style.display = "flex";
        loadSakuraFAQs();

        // -----------------------------
        // ★ 初回だけ初期メッセージを追加
        // -----------------------------
        if (!sakuraInitialAdded) {
            appendSakuraBubble(
                "sakura",
                "ナビゲーターのさくらです。HARUHIの使い方や思考モードの特徴など、何でも聞いてくださいね。"
            );
            sakuraInitialAdded = true;
        }

    } else {
        win.style.display = "none";
    }
}

// FAQ一覧ロード
async function loadSakuraFAQs() {
    const res = await fetch("/get_faqs");
    const data = await res.json();

    const faqList = document.getElementById("sakura-faq-list");
    faqList.innerHTML = "";

    data.faqs.forEach(faq => {
        const btn = document.createElement("button");
        btn.textContent = faq.question;

        btn.addEventListener("click", () => {
            document.getElementById("sakura-input").value = faq.question;
        });

        faqList.appendChild(btn);
    });
}

// さくらAIへ質問送信
async function sendSakuraFAQ() {
    const inputField = document.getElementById("sakura-input");
    const question = inputField.value.trim();
    if (!question) return;

    appendSakuraBubble("user", question);
    inputField.value = "";

    const res = await fetch("/sakura_faq_chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ question: question })
    });

    const data = await res.json();
    appendSakuraBubble("sakura", data.answer);
}

// 吹き出し描画
function appendSakuraBubble(role, text) {
    const area = document.getElementById("sakura-chat-area");

    const div = document.createElement("div");
    div.classList.add(role === "sakura" ? "sakura-bubble" : "user-bubble");
    div.textContent = text;

    area.appendChild(div);
    area.scrollTop = area.scrollHeight;
}
