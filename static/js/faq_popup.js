// static/js/faq_popup.js

document.addEventListener("DOMContentLoaded", async () => {
  const faqList = document.getElementById("faq-list");  // faq_popup.html 内の id=faq-list に FAQを入れる

  try {
    const res = await fetch("https://wsyyeqpnwoznwfmzydvl.supabase.co/rest/v1/haruhi_faqs?select=question,importance&order=importance.desc&limit=3", {
      headers: {
        apikey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzeXllcXBud296bndmbXp5ZHZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg1MjMzODMsImV4cCI6MjA2NDA5OTM4M30.b214yzmrZ2aTFK1CWlCb5wrZroUg2GBG9E_8E3D4hDE",
        Authorization: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzeXllcXBud296bndmbXp5ZHZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg1MjMzODMsImV4cCI6MjA2NDA5OTM4M30.b214yzmrZ2aTFK1CWlCb5wrZroUg2GBG9E_8E3D4hDE"
      }
    });

    const faqs = await res.json();

    // FAQボタン生成
    faqs.forEach(faq => {
      const btn = document.createElement("div");
      btn.className = "faq-item";
      btn.textContent = faq.question;

      // FAQクリック時の処理
      btn.addEventListener("click", async function() {
        const message = this.textContent;
        console.log("FAQクリック: ", message);

        const messagesDiv = document.getElementById("faq-chat-messages");

        // ユーザーのメッセージ表示
        const userMessageDiv = document.createElement("div");
        userMessageDiv.className = "faq-user-message";
        userMessageDiv.innerHTML = message;
        messagesDiv.appendChild(userMessageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        try {
          const res = await fetch("/sakura", {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
            body: `sakura_question=${encodeURIComponent(message)}&mode=faq`,
          });

          if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
          }

          const sakuraAnswer = await res.text();

          // さくらの返答を表示
          const sakuraReplyDiv = document.createElement("div");
          sakuraReplyDiv.className = "faq-sakura-message";
          sakuraReplyDiv.innerHTML = sakuraAnswer;
          messagesDiv.appendChild(sakuraReplyDiv);
          messagesDiv.scrollTop = messagesDiv.scrollHeight;

        } catch (err) {
          console.error("🌸さくらへの送信エラー", err);

          const errorDiv = document.createElement("div");
          errorDiv.className = "faq-sakura-message";
          errorDiv.innerHTML = "🌸 エラーが発生しました。";
          messagesDiv.appendChild(errorDiv);
          messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
      });

      // ボタンをリストに追加
      faqList.appendChild(btn);
    });

  } catch (e) {
    console.error("FAQの取得に失敗しました", e);
  }
});

// ✅ 通常の送信フォームからの送信はこちらで処理
async function sendFaqChatMessage(event) {
  event.preventDefault();

  const input = document.getElementById("faq-chat-input");
  const message = input.value.trim();

  if (!message) return;

  const messagesDiv = document.getElementById("faq-chat-messages");

  // 自分の発言を表示
  const userMessageDiv = document.createElement("div");
  userMessageDiv.className = "faq-user-message";
  userMessageDiv.innerHTML = message;
  messagesDiv.appendChild(userMessageDiv);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  // フォームをリセット
  input.value = "";

  try {
    const res = await fetch("/sakura", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: `sakura_question=${encodeURIComponent(message)}&mode=form`,
    });

    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    const sakuraAnswer = await res.text();

    // さくら回答を表示
    const sakuraReplyDiv = document.createElement("div");
    sakuraReplyDiv.className = "faq-sakura-message";
    sakuraReplyDiv.innerHTML = sakuraAnswer;
    messagesDiv.appendChild(sakuraReplyDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

  } catch (err) {
    console.error("さくらへの送信エラー", err);
    const errorDiv = document.createElement("div");
    errorDiv.className = "faq-sakura-message";
    errorDiv.innerHTML = "🌸 エラーが発生しました。";
    messagesDiv.appendChild(errorDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }
}
