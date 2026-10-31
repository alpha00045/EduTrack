// EduTrack interface interactions: theme, dashboard date, student search and flash alerts.
document.addEventListener("DOMContentLoaded", function () {
    // Keep a user's preferred appearance across visits.
    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");

    function applyTheme(theme) {
        const selected = theme === "dark" ? "dark" : "light";
        root.dataset.theme = selected;
        if (themeIcon) themeIcon.className = selected === "dark"
            ? "bi bi-sun-fill" : "bi bi-moon-stars";
        if (themeToggle) {
            const label = selected === "dark" ? "Switch to light mode" : "Switch to dark mode";
            themeToggle.setAttribute("aria-label", label);
            themeToggle.setAttribute("title", label);
        }
    }

    applyTheme(root.dataset.theme || "light");
    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            const next = root.dataset.theme === "dark" ? "light" : "dark";
            applyTheme(next);
            try { localStorage.setItem("edutrack-theme", next); } catch (_) { /* Storage may be disabled. */ }
        });
    }

    // Friendly local date on the dashboard.
    const dateTarget = document.getElementById("dashboardDate");
    if (dateTarget) {
        dateTarget.textContent = new Intl.DateTimeFormat(undefined, {
            weekday: "long", year: "numeric", month: "long", day: "numeric"
        }).format(new Date());
    }

    // Student list: search across visible fields and sort without losing row data.
    const table = document.getElementById("studentTable");
    const searchInput = document.getElementById("searchInput");
    const sortSelect = document.getElementById("sortSelect");
    if (table) {
        const tbody = table.querySelector("tbody");
        const noResults = document.getElementById("noSearchResults");
        const originalRows = Array.from(tbody.querySelectorAll("tr"))
            .filter(row => row.querySelector(".roll"));

        function updateList() {
            const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
            const sortBy = sortSelect ? sortSelect.value : "roll";
            const sortedRows = [...originalRows].sort((a, b) => {
                if (sortBy === "name") {
                    return a.querySelector(".name").innerText.trim().localeCompare(
                        b.querySelector(".name").innerText.trim()
                    );
                }
                if (sortBy === "average") {
                    return Number(b.querySelector(".average").innerText) -
                           Number(a.querySelector(".average").innerText);
                }
                return Number(a.querySelector(".roll").innerText) -
                       Number(b.querySelector(".roll").innerText);
            });

            let visibleCount = 0;
            sortedRows.forEach(row => {
                const matches = row.innerText.toLowerCase().includes(query);
                row.hidden = !matches;
                if (matches) {
                    visibleCount += 1;
                    const numberCell = row.querySelector(".row-number");
                    if (numberCell) numberCell.innerText = visibleCount;
                }
                tbody.appendChild(row);
            });
            if (noResults) noResults.classList.toggle("d-none", visibleCount !== 0);
        }

        if (originalRows.length) {
            if (searchInput) searchInput.addEventListener("input", updateList);
            if (sortSelect) sortSelect.addEventListener("change", updateList);
            updateList();
        }
    }

    // Show/hide the password on the login screen.
    const passwordInput = document.getElementById("loginPassword");
    const passwordToggle = document.getElementById("togglePassword");
    if (passwordInput && passwordToggle) {
        passwordToggle.addEventListener("click", function () {
            const show = passwordInput.type === "password";
            passwordInput.type = show ? "text" : "password";
            passwordToggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
            passwordToggle.innerHTML = show
                ? '<i class="bi bi-eye-slash" aria-hidden="true"></i>'
                : '<i class="bi bi-eye" aria-hidden="true"></i>';
        });
    }

    // Automatically dismiss Bootstrap flash messages.
    window.setTimeout(function () {
        document.querySelectorAll(".alert").forEach(function (alert) {
            if (window.bootstrap) window.bootstrap.Alert.getOrCreateInstance(alert).close();
        });
    }, 5000);
});
