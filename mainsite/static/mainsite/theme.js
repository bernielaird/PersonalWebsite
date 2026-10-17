// Dark mode button. Pages start light; clicking switches and remembers the choice.
// (A tiny inline script in each page's <head> applies a saved choice before the page draws.)
document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;
    const button = document.querySelector(".theme-toggle");
    if (!button) return;

    const isDark = () => root.dataset.theme === "dark";

    button.addEventListener("click", () => {
        const next = isDark() ? "light" : "dark";
        root.dataset.theme = next;
        try { localStorage.setItem("theme", next); } catch (e) { /* private mode: just don't remember */ }
        window.dispatchEvent(new Event("themechange"));
    });
});
