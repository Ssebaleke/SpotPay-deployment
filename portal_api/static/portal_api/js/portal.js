/**
 * portal.js
 * Handles package listing + inline payment modal.
 * Everything stays within the captive portal browser (hot.spot).
 */

const API_BASE = "{{API_BASE}}";
const LOCATION_UUID = "{{LOCATION_UUID}}";

document.addEventListener("DOMContentLoaded", function () {

    const endpoint = `${API_BASE}/portal/${LOCATION_UUID}/`;

    // ── Load packages ──────────────────────────────────────────────
    const tbody = document.querySelector("#packages-table tbody");
    if (tbody) {
        fetch(endpoint, { headers: { "Accept": "application/json" } })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(data => {
                tbody.innerHTML = "";
                if (!data.packages || data.packages.length === 0) {
                    tbody.innerHTML = "<tr><td colspan='3'>No packages available</td></tr>";
                    return;
                }
                data.packages.forEach(pkg => {
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td>${pkg.name}</td>
                        <td style="padding-right:10px;">UGX ${pkg.price}</td>
                        <td style="width:60px;"><button class="buy-btn" data-id="${pkg.id}" data-name="${pkg.name}" data-price="${pkg.price}">Buy</button></td>
                    `;
                    tbody.appendChild(row);
                });

                document.querySelectorAll(".buy-btn").forEach(btn => {
                    btn.addEventListener("click", function () {
                        openPayModal(this.dataset.id, this.dataset.name, this.dataset.price);
                    });
                });
            })
            .catch(() => {
                if (tbody) tbody.innerHTML = "<tr><td colspan='3'>Unable to load packages</td></tr>";
            });
    }

    // Support phone
    var sp = document.getElementById("support-phone");
    if (sp && window.SUPPORT_PHONE) {
        sp.textContent = window.SUPPORT_PHONE;
        sp.href = "tel:" + window.SUPPORT_PHONE;
    }
});


// ── Payment Modal ──────────────────────────────────────────────────

function openPayModal(pkgId, pkgName, pkgPrice) {
    document.getElementById("modal-pkg-name").textContent = pkgName;
    document.getElementById("modal-pkg-price").textContent = pkgPrice;
    document.getElementById("modal-phone").value = "";
    document.getElementById("modal-pkg-id").value = pkgId;
    setModalState("form");
    document.getElementById("pay-modal").style.display = "flex";
}

function closePayModal() {
    document.getElementById("pay-modal").style.display = "none";
    clearInterval(window._pollTimer);
}

function setModalState(state) {
    document.getElementById("modal-form-section").style.display    = state === "form"    ? "block" : "none";
    document.getElementById("modal-waiting-section").style.display = state === "waiting" ? "block" : "none";
    document.getElementById("modal-success-section").style.display = state === "success" ? "block" : "none";
    document.getElementById("modal-error-section").style.display   = state === "error"   ? "block" : "none";
}

function submitPayment() {
    var phone = document.getElementById("modal-phone").value.trim();
    var pkgId = document.getElementById("modal-pkg-id").value;

    if (!phone) { alert("Please enter your phone number"); return; }

    setModalState("waiting");
    document.getElementById("modal-waiting-msg").textContent = "Sending payment prompt to " + phone + "...";

    var buyUrl = API_BASE + "/portal/" + LOCATION_UUID + "/buy/";
    var urlParams = new URLSearchParams(window.location.search);

    fetch(buyUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            package_id: parseInt(pkgId),
            phone: phone,
            mac_address: urlParams.get("mac") || "",
            ip_address: urlParams.get("ip") || "",
        })
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showModalError(data.message || "Payment failed. Please try again.");
            return;
        }
        document.getElementById("modal-waiting-msg").textContent = "Approve the prompt on your phone...";
        pollPaymentStatus(data.status_url, data.payment_uuid);
    })
    .catch(() => showModalError("Network error. Please try again."));
}

function pollPaymentStatus(statusUrl, paymentUuid) {
    var attempts = 0;
    clearInterval(window._pollTimer);
    window._pollTimer = setInterval(function () {
        if (++attempts > 60) {
            clearInterval(window._pollTimer);
            showModalError("Timed out waiting for payment. Please try again.");
            return;
        }
        fetch(statusUrl)
            .then(r => r.json())
            .then(data => {
                if (data.status === "SUCCESS") {
                    clearInterval(window._pollTimer);
                    onPaymentSuccess(data.voucher, data.hotspot_dns);
                } else if (data.status === "FAILED" || data.status === "CANCELLED") {
                    clearInterval(window._pollTimer);
                    showModalError("Payment failed or was cancelled. Please try again.");
                }
            })
            .catch(() => {});
    }, 2000);
}

function onPaymentSuccess(voucherCode, hotspotDns) {
    setModalState("success");
    document.getElementById("modal-voucher-code").textContent = voucherCode || "";

    if (!voucherCode) {
        document.getElementById("modal-success-msg").textContent = "Payment confirmed! Your voucher will be sent via SMS.";
        return;
    }

    document.getElementById("modal-success-msg").textContent = "Payment confirmed! Connecting you...";
    setTimeout(function () { autoLogin(voucherCode); }, 1000);
}

function autoLogin(voucherCode) {
    var loginType = window.LOGIN_TYPE || "PLAIN";
    var form = document.login;
    if (!form) return;
    form.username.value = voucherCode;
    if (loginType === "NONE") {
        form.password.value = "";
        form.submit();
    } else if (loginType === "CHAP" && typeof doLogin === "function") {
        // CHAP requires MD5 hash — delegate to MikroTik's doLogin()
        form.password.value = voucherCode;
        doLogin();
    } else {
        // PLAIN or SEPARATE
        form.password.value = voucherCode;
        form.submit();
    }
}

function showModalError(msg) {
    setModalState("error");
    document.getElementById("modal-error-msg").textContent = msg;
}
