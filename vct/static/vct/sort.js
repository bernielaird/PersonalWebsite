// Click a column header in a table.sortable to sort by it; click again to flip. Blank cells always go last.
document.querySelectorAll("table.sortable").forEach(table => {
    const headers = [...table.tHead.rows[0].cells];
    const body = table.tBodies[0];
    const value = (row, i) => {
        const cell = row.cells[i];
        if (!cell) return "";
        const text = (cell.dataset.v ?? cell.textContent).trim();
        const n = parseFloat(text.replace("−", "-").replace(/[+,%]/g, ""));
        return /^[−+\-]?[\d.,]+%?$/.test(text.split(/\s/)[0]) && !isNaN(n) ? n : text.toLowerCase();
    };
    headers.forEach((th, i) => {
        th.classList.add("sort-header");
        th.addEventListener("click", () => {
            const dir = th.dataset.dir === "desc" ? "asc" : "desc";
            headers.forEach(h => delete h.dataset.dir);
            th.dataset.dir = dir;
            const rows = [...body.rows].filter(r => r.cells.length === headers.length);
            rows.sort((a, b) => {
                const x = value(a, i), y = value(b, i);
                if (x === "" || y === "") return x === "" ? (y === "" ? 0 : 1) : -1;
                const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
                return dir === "asc" ? c : -c;
            });
            rows.forEach(r => body.appendChild(r));
        });
    });
});
