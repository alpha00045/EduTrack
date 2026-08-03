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

setTimeout(function () {

    let alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        let bsAlert = bootstrap.Alert.getOrCreateInstance(alert);

        bsAlert.close();

    });

}, 3500);
