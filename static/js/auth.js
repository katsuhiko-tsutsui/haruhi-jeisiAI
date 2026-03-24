// Supabase設定（公開キーなのでJSに書いてOK）
const SUPABASE_URL = "https://wsyyeqpnwoznwfmzydvl.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzeXllcXBud296bndmbXp5ZHZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg1MjMzODMsImV4cCI6MjA2NDA5OTM4M30.b214yzmrZ2aTFK1CWlCb5wrZroUg2GBG9E_8E3D4hDE";

// タブ切り替え
function switchTab(tab) {
    document.getElementById("form-login").style.display  = tab === "login"  ? "block" : "none";
    document.getElementById("form-signup").style.display = tab === "signup" ? "block" : "none";
    document.getElementById("tab-login").classList.toggle("active",  tab === "login");
    document.getElementById("tab-signup").classList.toggle("active", tab === "signup");
}

// ログイン処理
async function handleLogin() {
    const email    = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const msg      = document.getElementById("login-msg");

    if (!email || !password) {
        msg.className = "msg error";
        msg.textContent = "メールアドレスとパスワードを入力してください";
        return;
    }

    msg.className = "msg";
    msg.textContent = "ログイン中...";

    const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY
        },
        body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (data.access_token) {
        // トークンをsessionStorageに保存
        sessionStorage.setItem("haruhi_access_token", data.access_token);
        sessionStorage.setItem("haruhi_user_id", data.user.id);
        sessionStorage.setItem("haruhi_email", data.user.email);
        // チャット画面へ遷移（トークンをURLパラメータで渡す）
        window.location.href = "/?token=" + data.access_token;
    } else {
        msg.className = "msg error";
        msg.textContent = "ログインに失敗しました。メールアドレスかパスワードを確認してください。";
    }
}

// 新規登録処理
async function handleSignup() {
    const email    = document.getElementById("signup-email").value.trim();
    const password = document.getElementById("signup-password").value;
    const msg      = document.getElementById("signup-msg");

    if (!email || !password) {
        msg.className = "msg error";
        msg.textContent = "メールアドレスとパスワードを入力してください";
        return;
    }
    if (password.length < 8) {
        msg.className = "msg error";
        msg.textContent = "パスワードは8文字以上にしてください";
        return;
    }

    msg.className = "msg";
    msg.textContent = "登録中...";

    const res = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY
        },
        body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (data.id || data.user) {
        msg.className = "msg success";
        msg.textContent = "確認メールを送信しました。メールのリンクをクリックして登録を完了してください。";
    } else {
        msg.className = "msg error";
        msg.textContent = "登録に失敗しました：" + (data.msg || data.message || "不明なエラー");
    }
}