// Buy calculator: fetches the precomputed grid for the chosen round / score / side / last result once,
// then interpolates between money levels in the browser as the credits change.
(function () {
    const form = document.getElementById("calc");
    const body = document.getElementById("calc-body");
    const verdict = document.getElementById("calc-verdict");
    const warning = document.getElementById("calc-warning");
    const levels = JSON.parse(document.getElementById("calc-levels").textContent);
    const options = JSON.parse(document.getElementById("calc-options").textContent);
    const STATS = 4;  // map, round, if_win, if_lose per option
    const LABELS = { eco: "save (eco)", half: "half buy", force: "force", full: "full buy", bonus: "bonus" };
    const ORDER = ["round", "map", "if_win", "if_lose"];  // table column order, as stat indexes below
    const COL = { map: 0, round: 1, if_win: 2, if_lose: 3 };
    const TOO_CLOSE = 2;  // points: about the simulation noise
    const cache = new Map();
    const f = (name) => form.elements[name];

    function opt(select, value, text) {
        const o = document.createElement("option");
        o.value = value;
        o.textContent = text;
        select.appendChild(o);
    }

    function fillScores() {
        const r = +f("round").value, sel = f("score"), prev = sel.value;
        sel.innerHTML = "";
        let even = null;
        for (let s = Math.max(0, r - 13); s <= Math.min(12, r - 1); s++) {
            opt(sel, s, `${s}–${r - 1 - s}`);
            if (even === null || Math.abs(s - (r - 1 - s)) < Math.abs(even - (r - 1 - even))) even = s;
        }
        sel.value = [...sel.options].some((o) => o.value === prev) ? prev : even;
    }

    function fillLast() {
        const r = +f("round").value, s = +f("score").value, o = r - 1 - s, sel = f("last"), prev = sel.value;
        const halfRounds = r < 13 ? r - 1 : r - 13;
        const pistolNext = r === 2 || r === 14;
        document.getElementById("last-label").textContent = pistolNext ? "Pistol round" : "Last round";
        sel.innerHTML = "";
        if (pistolNext) {
            opt(sel, 1, "you won it");
            opt(sel, -1, "you lost it");
        } else {
            for (let k = 1; k <= Math.min(3, halfRounds, s); k++)
                opt(sel, k, k === 1 ? "you won it" : `you won it, they've lost ${k}${k === 3 ? "+" : ""} in a row`);
            for (let k = 1; k <= Math.min(3, halfRounds, o); k++)
                opt(sel, -k, k === 1 ? "you lost it" : `you've lost ${k}${k === 3 ? "+" : ""} in a row`);
        }
        sel.value = [...sel.options].some((x) => x.value === prev) ? prev : sel.options[0].value;
    }

    async function cells() {
        const q = new URLSearchParams({ round: f("round").value, score: f("score").value,
                                        side: f("side").value, last: f("last").value });
        const key = q.toString();
        if (!cache.has(key)) {
            cache.set(key, fetch(`${window.CALC_URL}?${key}`).then((r) => r.json()).then((d) => d.cells));
        }
        return cache.get(key);
    }

    function bracket(x) {
        if (x <= levels[0]) return [levels[0], levels[0], 0];
        const last = levels[levels.length - 1];
        if (x >= last) return [last, last, 0];
        for (let i = 0; i < levels.length - 1; i++) {
            if (x <= levels[i + 1]) return [levels[i], levels[i + 1], (x - levels[i]) / (levels[i + 1] - levels[i])];
        }
    }

    // Values for (bank, opp): bilinear between the four surrounding grid points that exist; the nearest
    // grid point decides which buys are possible and fills in where no surrounding point has a value.
    function lookup(rows, bank, opp) {
        const at = new Map(rows.map((c) => [`${c[0]},${c[1]}`, c]));
        const [x0, x1, tx] = bracket(bank), [y0, y1, ty] = bracket(opp);
        const corners = [[x0, y0, (1 - tx) * (1 - ty)], [x1, y0, tx * (1 - ty)],
                         [x0, y1, (1 - tx) * ty], [x1, y1, tx * ty]];
        let nearest = null, best = Infinity;
        for (const c of rows) {
            const d = (c[0] - bank) ** 2 + (c[1] - opp) ** 2;
            if (d < best) { best = d; nearest = c; }
        }
        const out = {};
        options.forEach((o, k) => {
            const base = 2 + k * STATS;
            if (nearest[base] === null) return;
            const vals = [];
            for (let j = 0; j < STATS; j++) {
                let num = 0, den = 0;
                for (const [x, y, w] of corners) {
                    const c = at.get(`${x},${y}`);
                    if (w > 0 && c && c[base + j] !== null) { num += w * c[base + j]; den += w; }
                }
                vals.push(den > 1e-9 ? num / den : nearest[base + j]);
            }
            out[o] = vals;
        });
        return { values: out, nearest, distance: Math.sqrt(best) };
    }

    const pct = (v) => (v === null || Number.isNaN(v) ? "–" : `${v.toFixed(1)}%`);
    const money = (v) => v.toLocaleString("en-US");

    async function update() {
        const params = new URLSearchParams(new FormData(form));
        history.replaceState(null, "", `?${params}`);
        const rows = await cells();
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="5" class="muted">No pro games reached this spot.</td></tr>';
            verdict.textContent = warning.textContent = "";
            return;
        }
        const bank = Math.max(0, +f("bank").value || 0), opp = Math.max(0, +f("opp").value || 0);
        const { values, nearest, distance } = lookup(rows, bank, opp);
        const shown = options.filter((o) => values[o]);
        const ranked = [...shown].sort((a, b) => values[b][COL.map] - values[a][COL.map]);
        body.innerHTML = "";
        for (const o of shown) {
            const tr = document.createElement("tr");
            if (o === ranked[0]) tr.className = "calc-best";
            tr.innerHTML = `<td>${LABELS[o]}</td>` +
                ORDER.map((s) => `<td class="num">${pct(values[o][COL[s]])}</td>`).join("");
            body.appendChild(tr);
        }
        if (ranked.length > 1) {
            const gap = values[ranked[0]][COL.map] - values[ranked[1]][COL.map];
            verdict.innerHTML = gap < TOO_CLOSE
                ? `<b>Too close to call:</b> ${LABELS[ranked[0]]} and ${LABELS[ranked[1]]} are ${gap.toFixed(1)} points apart for the map, within the simulation noise.`
                : `<b>Best for the map: ${LABELS[ranked[0]]}</b>, by ${gap.toFixed(1)} points over ${LABELS[ranked[1]]}.`;
        } else {
            verdict.innerHTML = ranked.length ? `Only one option here: <b>${LABELS[ranked[0]]}</b>.` : "";
        }
        warning.textContent = distance > 3000
            ? `No pro team had about this much money in this spot; showing the closest we have (you ${money(nearest[0])}, them ${money(nearest[1])}).`
            : "";
    }

    function load() {
        const q = new URLSearchParams(location.search);
        if (q.has("round") && [...f("round").options].some((o) => o.value === q.get("round"))) f("round").value = q.get("round");
        else f("round").value = "8";
        fillScores();
        if (q.has("score")) f("score").value = q.get("score");
        if (!f("score").value) fillScores();
        if (q.get("side") === "def") f("side").value = "def";
        fillLast();
        if (q.has("last") && [...f("last").options].some((o) => o.value === q.get("last"))) f("last").value = q.get("last");
        if (q.has("bank")) f("bank").value = q.get("bank");
        if (q.has("opp")) f("opp").value = q.get("opp");
        update();
    }

    f("round").addEventListener("change", () => { fillScores(); fillLast(); update(); });
    f("score").addEventListener("change", () => { fillLast(); update(); });
    for (const name of ["side", "last"]) f(name).addEventListener("change", update);
    for (const name of ["bank", "opp"]) f(name).addEventListener("input", update);
    load();
})();
