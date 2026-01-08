document.getElementById("loginBtn").onclick = async () => {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const error = document.getElementById("error");

    error.innerText = "";

    const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });

    const data = await res.json();

    if (!res.ok) {
        error.innerText = data.detail;
        return;
    }

    localStorage.setItem("username", data.username);
    localStorage.setItem("role", data.role);

    if (data.role === "admin") {
        location.href = "/static/admin.html";
    } else {
        location.href = "/static/dashboard.html";
    }
};
