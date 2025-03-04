document.addEventListener("DOMContentLoaded", function () {
    // Function to extract URL parameters and populate form fields
    function getQueryParam(param) {
        let urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(param) || '';
    }

    // Autofill form fields with URL parameters
    document.getElementById("serial_number").value = getQueryParam("serial_number");
    document.getElementById("customer_name").value = getQueryParam("customer_name");
    document.getElementById("service_location").value = getQueryParam("service_location");
    document.getElementById("region").value = getQueryParam("region");
    document.getElementById("asset_Description").value = getQueryParam("asset_Description");

    // Serial number validation and autofill additional data
    $("#serial_number").change(function () {
        let serial = $(this).val();
        $.get("/ticket1/check_serial/" + serial, function (data) {
            $("#customer_name").val(data.customer_name);
            $("#service_location").val(data.service_location);
            $("#region").val(data.region);
            $("#asset_Description").val(data.asset_Description);
        }).fail(function () {
            $("#serial_status").text("Serial Number not found!");
        });
    });

    // Attach event listener to the reset button
    document.getElementById("resetButton").addEventListener("click", function () {
        document.getElementById("serial_number").value = "";
        document.getElementById("customer_name").value = "";
        document.getElementById("service_location").value = "";
        document.getElementById("region").value = "";
        document.getElementById("assetResults").innerHTML = `<tr><td colspan='6' class='text-center'>No results found.</td></tr>`;
    });

    // Attach event listener for Enter key press
    let searchInputs = document.querySelectorAll("#serial_number, #customer_name, #service_location, #region");
    searchInputs.forEach(input => {
        input.addEventListener("keypress", function (event) {
            if (event.key === "Enter") {
                event.preventDefault(); // Prevent form submission
                searchAssets();
            }
        });
    });

    // Attach event listener to search button
    document.getElementById("searchButton").addEventListener("click", function () {
        searchAssets();
    });
});

// Function to handle asset search
function searchAssets() {
    let serialNo = document.getElementById("serial_number").value.trim();
    let customerName = document.getElementById("customer_name").value.trim();
    let serviceLocation = document.getElementById("service_location").value.trim();
    let region = document.getElementById("region").value.trim();

    // Prevent empty search requests
    if (!serialNo && !customerName && !serviceLocation && !region) {
        alert("Please enter at least one search criteria.");
        return;
    }

    fetch("/tickets/search_assets", {
        method: "POST",
        body: JSON.stringify({
            serial_number: serialNo,
            customer_name: customerName,
            service_location: serviceLocation,
            region: region
        }),
        headers: { "Content-Type": "application/json" }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP Error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        let tableBody = document.getElementById("assetResults");
        tableBody.innerHTML = "";

        if (data.message) {
            tableBody.innerHTML = `<tr><td colspan='6' class='text-center text-danger'>${data.message}</td></tr>`;
            return;
        }

        data.forEach(asset => {
            let row = `<tr>
                <td>${asset.serial_number}</td>
                <td>${asset.customer_name}</td>
                <td>${asset.service_location}</td>
                <td>${asset.region}</td>
                <td>${asset.asset_description}</td>
                <td>
                    <button class="btn btn-success btn-sm"
                        onclick="new_ticket('${asset.serial_number}', '${asset.customer_name}', '${asset.service_location}', '${asset.region}', '${asset.asset_description}')">
                        Make Ticket
                    </button>
                </td>
            </tr>`;
            tableBody.innerHTML += row;
        });
    })
    .catch(error => {
        console.error("Error fetching assets:", error);
        let tableBody = document.getElementById("assetResults");
        tableBody.innerHTML = `<tr><td colspan='6' class='text-center text-danger'>An error occurred. Please try again.</td></tr>`;
    });
}
function fetchReport() {
    let startDate = $("#start_date").val();
    let endDate = $("#end_date").val();
    let technicianId = $("#technician").val();

    $.get(`/reports/data?start_date=${startDate}&end_date=${endDate}&technician_id=${technicianId}`, function(data) {
        let reportBody = $("#report_body");
        reportBody.empty();
        data.forEach(row => {
            reportBody.append(`
                <tr>
                    <td>${row.technician_name}</td>
                    <td>${row.pm_done}</td>
                    <td>${row.cm_done}</td>
                    <td>${row.installations_done}</td>
                    <td>${row.myq_installations_done}</td>
                    <td>${row.other_tickets_done}</td>
                </tr>
            `);
        });
    });
}
function showTechnicianReport() {
    console.log("showTechnicianReport function called!");

    fetch("/report/data")
        .then(response => response.json())
        .then(data => {
            console.log("Data received:", data);

            let tableBody = document.getElementById("reportTableBody");
            if (!tableBody) {
                console.error("Table body not found!");
                return;
            }

            tableBody.innerHTML = ""; // Clear old data

            data.forEach(row => {
                let newRow = `<tr>
                    <td>${row.technician_name}</td>
                    <td>${row.pm_done}</td>
                    <td>${row.cm_done}</td>
                    <td>${row.installations_done}</td>
                    <td>${row.myq_installations_done}</td>
                    <td>${row.other_tickets_done}</td>
                </tr>`;
                tableBody.innerHTML += newRow;
            });
        })
        .catch(error => console.error("Error fetching report data:", error));
}

// Redirect function to pre-fill ticket form with asset data
function new_ticket(serial_number, customer_name, service_location, region, asset_description) {
    let url = `/ticket1/new_auto_populated_ticket?serial_number=${encodeURIComponent(serial_number)}&customer_name=${encodeURIComponent(customer_name)}&service_location=${encodeURIComponent(service_location)}&region=${encodeURIComponent(region)}&asset_Description=${encodeURIComponent(asset_description)}`;
    window.location.href = url; // Redirect to the new pre-populated ticket form
}
