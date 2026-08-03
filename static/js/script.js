const searchInput = document.getElementById("searchInput");

if (searchInput) {

    searchInput.addEventListener("keyup", function () {

        const filter = this.value.toLowerCase().trim();

        const rows = document.querySelectorAll("#studentTable tbody tr");

        rows.forEach(function (row) {

            const roll = row.querySelector(".roll").innerText.toLowerCase();

            const name = row.querySelector(".name").innerText.toLowerCase();

            const grade = row.querySelector(".grade").innerText.toLowerCase();

            if (
                roll.includes(filter) ||
                name.includes(filter) ||
                grade.includes(filter)
            ) {

                row.style.display = "";

            } else {

                row.style.display = "none";

            }

        });

    });

}

const sortSelect = document.getElementById("sortSelect");

if (sortSelect) {

    sortSelect.addEventListener("change", function () {

        const tbody = document.querySelector("#studentTable tbody");

        const rows = Array.from(tbody.querySelectorAll("tr"));

        const sortBy = this.value;

        rows.sort(function (a, b) {

            if (sortBy === "roll") {

                const rollA = parseInt(a.querySelector(".roll").innerText);
                const rollB = parseInt(b.querySelector(".roll").innerText);

                return rollA - rollB;
            }

            if (sortBy === "name") {

                const nameA = a.querySelector(".name").innerText.toLowerCase();
                const nameB = b.querySelector(".name").innerText.toLowerCase();

                return nameA.localeCompare(nameB);
            }

            if (sortBy === "average") {

                const avgA = parseFloat(a.cells[6].innerText);
                const avgB = parseFloat(b.cells[6].innerText);

                return avgB - avgA;
            }

        });

        rows.forEach(function (row) {

            tbody.appendChild(row);

        });

    });

}

setTimeout(function () {

    let alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        let bsAlert = bootstrap.Alert.getOrCreateInstance(alert);

        bsAlert.close();

    });

}, 3500);
