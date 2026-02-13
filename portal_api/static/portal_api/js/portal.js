alert("portal.js loaded");

document.addEventListener("DOMContentLoaded", function () {

    const endpoint = `${window.API_BASE}${window.LOCATION_UUID}/`;
    const table = document.getElementById("packages-table");
    const tbody = table?.querySelector("tbody");

    if (!tbody) {
        console.error("packages-table tbody not found");
        return;
    }

    fetch(endpoint)
        .then(res => {
            if (!res.ok) throw new Error("API error");
            return res.json();
        })
        .then(data => {
            console.log("Data received:", data);

            tbody.innerHTML = "";

            if (!data.packages || data.packages.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="2">No packages available</td>
                    </tr>
                `;
                return;
            }

            data.packages.forEach(pkg => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${pkg.name}</td>
                    <td>UGX ${pkg.price}</td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(err => {
            console.error("Package load error:", err);
            tbody.innerHTML = `
                <tr>
                    <td colspan="2">Failed to load packages</td>
                </tr>
            `;
        });

});
