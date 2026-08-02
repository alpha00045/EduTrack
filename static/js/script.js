document
.getElementById("searchInput")
.addEventListener("keyup", function () {

    let filter =
        this.value.toLowerCase();

    let rows =
        document.querySelectorAll(
            "#studentTable tbody tr"
        );

    rows.forEach(function (row) {

        let text =
            row.innerText.toLowerCase();

        if (text.includes(filter)) {

            row.style.display = "";

        }

        else {

            row.style.display = "none";

        }

    });

});

setTimeout(function () {

    let alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        let bsAlert = bootstrap.Alert.getOrCreateInstance(alert);

        bsAlert.close();

    });

}, 3500);
