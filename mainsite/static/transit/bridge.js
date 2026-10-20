// Connects the original front end (sketch.js) to the simulator compiled to JavaScript (vts.js), in place
// of the websocket to the Java server. Messages go both ways asynchronously, like they would over a socket.
// window.VTS_FILES can point at the config file (the website does, for its own static file URLs).
(function () {
    const files = Object.assign({ config: "config.txt", map: "map.png" }, window.VTS_FILES || {});

    // The same view as the original Mapbox static image: 900x600, centered on campus, Mapbox zoom 13.
    const VIEW = { lat: 44.9765, lng: -93.215, width: 900, height: 600, world: 512 * Math.pow(2, 13) };
    function worldXY(lat, lng) {
        const s = Math.sin(lat * Math.PI / 180);
        return {
            x: (lng + 180) / 360 * VIEW.world,
            y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * VIEW.world,
        };
    }
    const center = worldXY(VIEW.lat, VIEW.lng);

    window.VtsBridge = {
        mapUrl: files.map,
        mapWidth: VIEW.width,
        mapHeight: VIEW.height,
        // Pixel position on the map image, like mappa's staticMap.latLngToPixel.
        latLngToPixel(lat, lng) {
            const p = worldXY(lat, lng);
            return { x: p.x - center.x + VIEW.width / 2, y: p.y - center.y + VIEW.height / 2 };
        },
        // A stand-in for the websocket: send(), plus the onopen / onmessage the sketch sets.
        connect() {
            const socket = {
                onopen: null,
                onmessage: null,
                send(message) {
                    if (window.vtsSend) window.vtsSend(message);
                },
            };
            window.vtsReceive = (message) => {
                setTimeout(() => socket.onmessage && socket.onmessage({ data: message }), 0);
            };
            fetch(files.config)
                .then((r) => r.text())
                .then((text) => {
                    window.VTS_CONFIG = text;
                    main([]);  // vts.js: starts the simulation session and defines window.vtsSend
                    if (socket.onopen) socket.onopen();
                });
            return socket;
        },
    };
})();
