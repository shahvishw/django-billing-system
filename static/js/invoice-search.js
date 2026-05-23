const searchInput = document.getElementById("invoiceSearch");

if (searchInput) {

    searchInput.addEventListener("keyup", function () {

        const searchValue = this.value.toLowerCase();

        const rows = document.querySelectorAll(".invoice-row");

        rows.forEach((row) => {

            const invoiceNumber = row
                .querySelector(".invoice-number")
                .innerText.toLowerCase();

            const customerName = row
                .querySelector(".customer-name")
                .innerText.toLowerCase();

            const invoiceStatus = row
                .querySelector(".invoice-status")
                .innerText.toLowerCase();

            if (
                invoiceNumber.includes(searchValue) ||
                customerName.includes(searchValue) ||
                invoiceStatus.includes(searchValue)
            ) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }

        });

    });

}