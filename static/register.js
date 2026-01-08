document.getElementById("registerBtn").onclick = async () => {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const error = document.getElementById("error");

    error.innerText = "";

    const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });

    const data = await res.json();

    if (!res.ok) {
        error.innerText = data.detail;
        return;
    }

    alert("Registered! Please login.");
    location.href = "login.html";
};
