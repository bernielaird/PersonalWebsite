document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("loaded");

    document.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", function(e) {
            if (this.hostname === window.location.hostname) {
                e.preventDefault();
                document.body.classList.add("fade-out");
                setTimeout(() => {
                    window.location = this.href;
                }, 200);
            }
        });
    });
});