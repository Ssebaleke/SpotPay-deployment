document.addEventListener("DOMContentLoaded", function () {

    const slides = document.getElementById("ads-slides");
    if (!slides) {
        console.warn("Ads container not found");
        return;
    }

    if (!window.API_BASE || !window.LOCATION_UUID) {
        console.error("Missing API_BASE or LOCATION_UUID");
        return;
    }

    const url = window.API_BASE + window.LOCATION_UUID + "/";

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error("Ads API error: " + response.status);
            }
            return response.json();
        })
        .then(data => {
            slides.innerHTML = "";

            if (!data.ads || data.ads.length === 0) {
                slides.innerHTML = `<div class="slide">No ads available</div>`;
                return;
            }

            data.ads.forEach(ad => {
                const slide = document.createElement("div");
                slide.className = "slide";

                slide.innerHTML = `
                    <img src="${ad.url}"
                         alt="Advertisement"
                         style="width:100%; border-radius:12px;">
                `;

                slides.appendChild(slide);
            });
        })
        .catch(error => {
            console.error("Failed to load ads:", error);
            slides.innerHTML =
                `<div class="slide">Ads unavailable</div>`;
        });

});
