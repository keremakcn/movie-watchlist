document.addEventListener("DOMContentLoaded", function () {
    const currentUrl = window.location.href;
    const filterLinks = document.querySelectorAll(".filter-group a");

    for (const link of filterLinks) {
        if (link.href === currentUrl) {
            link.classList.add("active-filter");
        }
    }
});
