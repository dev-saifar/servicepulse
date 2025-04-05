function loadTonerModels() {
    const tonerType = document.getElementById("toner_type").value;
    const modelDropdown = document.getElementById("toner_model");
    modelDropdown.innerHTML = "";

    fetch("/toner/get_toner_models", {
        method: "POST",
        body: JSON.stringify({
            model: document.getElementById("asset_description").value,
            toner_type: tonerType
        }),
        headers: {
            "Content-Type": "application/json"
        }
    }).then(res => res.json())
      .then(data => {
        data.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.model;
            opt.text = item.model;
            modelDropdown.appendChild(opt);
        });
    });
}

function submitTonerRequest(event) {
    event.preventDefault();

    const payload = {
        serial_number: document.getElementById("serial_number").value,
        asset_code: document.getElementById("asset_code").value,
        asset_description: document.getElementById("asset_description").value,
        customer_name: document.getElementById("customer_name").value,
        service_location: document.getElementById("service_location").value,
        region: document.getElementById("region").value,
        billing_company: document.getElementById("billing_company").value,
        contract_code: document.getElementById("contract_code").value,
        toner_type: document.getElementById("toner_type").value,
        toner_model: document.getElementById("toner_model").value,
        toner_source: document.getElementById("toner_source").value,
        issued_qty: document.getElementById("issued_qty").value,
        meter_reading: document.getElementById("meter_reading").value,
        'previous_reading': row.find(".prev_reading").text().trim() || 0,

        requested_by: document.getElementById("requested_by").value,
        comments: document.getElementById("comments").value
    };

    fetch('/toner/submit_bulk_request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(result => {
    if (result.success) {
        window.location.href = `/toner/print_request/${result.request_group}`;
    } else {
        alert("Error: " + result.error);
    }
});

}
