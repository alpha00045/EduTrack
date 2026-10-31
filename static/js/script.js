// Student list: search across all visible fields and sort without losing row data.
document.addEventListener("DOMContentLoaded", function () {
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
                    row.querySelector(".row-number").innerText = visibleCount;
                }
                tbody.appendChild(row);
            });

            if (noResults) {
                noResults.classList.toggle("d-none", visibleCount !== 0);
            }
        }

        if (searchInput) searchInput.addEventListener("input", updateList);
        if (sortSelect) sortSelect.addEventListener("change", updateList);
        updateList();
    }

    // Automatically dismiss Bootstrap flash messages after a short delay.
    window.setTimeout(function () {
        document.querySelectorAll(".alert").forEach(function (alert) {
            if (window.bootstrap) {
                window.bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        });
    }, 3500);
});
