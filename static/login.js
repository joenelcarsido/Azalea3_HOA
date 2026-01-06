document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("loginBtn");

    btn.addEventListener("click", async () => {
        console.log("Login clicked");

        const username = document.getElementById("username").value;
        const password = document.getElementById("password").value;
        const errorDiv = document.getElementById("error");

        errorDiv.innerText = "";

        try {
            const res = await fetch("/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    username,
                    password
                })
            });

            const data = await res.json();
            console.log("RAW RESPONSE:", data);

            if (!res.ok) {
                errorDiv.innerText = data.detail || "Login failed";
                return;
            }

            alert("Login successful!");
            localStorage.setItem("token", data.token);
            window.location.href = "/static/dashboard.html";

        } catch (err) {
            console.error(err);
            errorDiv.innerText = "Server error";
        }
    });
});
