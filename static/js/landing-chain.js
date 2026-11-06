/* O caminho é decorativo. A leitura e os links funcionam sem JavaScript. */
(() => {
    'use strict';
    const layer = document.querySelector('[data-scroll-chain]');
    if (!layer || !window.requestAnimationFrame) return;
    const svg = layer.querySelector('svg');
    const track = layer.querySelector('[data-chain-track]');
    const fill = layer.querySelector('[data-chain-fill]');
    const head = layer.querySelector('[data-chain-head]');
    const stops = Array.from(document.querySelectorAll('[data-chain-stop]'));
    if (!stops.length) return;
    const root = document.documentElement;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const desktop = window.matchMedia('(min-width: 761px)');
    let enabled = false;
    let dirty = true;
    let frame;
    let length = 0;
    let origin = 0;
    let viewport = 0;
    let lastScroll = 0;
    let points = [];
    let printing = false;
    let previousOffset;
    let previousOpacity;
    let previousX;
    let previousY;

    // Aproxima as curvas apenas quando o layout muda, com erro geométrico
    // limitado a 0,15 px. Na rolagem, usamos somente esta tabela em memória.
    const appendPoint = point => {
        const previous = points[points.length - 1];
        const distance = previous ? Math.hypot(point.x - previous.x, point.y - previous.y) : 0;
        if (previous && distance < .000001) return;
        length += distance;
        points.push({ x: point.x, y: point.y, distance: length });
    };
    const midpoint = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
    const flattenCurve = (a, b, c, d, depth = 0) => {
        const chord = Math.hypot(d.x - a.x, d.y - a.y);
        const deviation = point => chord ? Math.abs((d.x - a.x) * (a.y - point.y) - (a.x - point.x) * (d.y - a.y)) / chord : Math.hypot(point.x - a.x, point.y - a.y);
        if (depth >= 12 || Math.max(deviation(b), deviation(c)) <= .15) {
            appendPoint(d);
            return;
        }
        const ab = midpoint(a, b), bc = midpoint(b, c), cd = midpoint(c, d);
        const abc = midpoint(ab, bc), bcd = midpoint(bc, cd);
        const middle = midpoint(abc, bcd);
        flattenCurve(a, ab, abc, middle, depth + 1);
        flattenCurve(middle, bcd, cd, d, depth + 1);
    };

    const measure = () => {
        const bounds = layer.getBoundingClientRect();
        const width = bounds.width;
        if (!width || !bounds.height) return;
        origin = bounds.top + window.scrollY;
        viewport = window.innerHeight;
        lastScroll = Math.max(0, root.scrollHeight - viewport - 1);
        const rail = Math.max(18, (width - 1240) / 2 + 18);
        // Todas as leituras de layout precedem as alterações no SVG.
        const sections = stops.map(stop => {
            const rect = stop.getBoundingClientRect();
            return { top: rect.top - bounds.top, height: rect.height,
                gap: stop.previousElementSibling.getBoundingClientRect().height };
        });
        points = [];
        length = 0;
        let x = width / 2;
        let d = '';
        sections.forEach((section, index) => {
            const { top, height, gap } = section;
            // Absorve diferenças subpixel entre retângulos vizinhos.
            const start = Math.max(top - gap, points[points.length - 1]?.y ?? -Infinity);
            const nextX = index % 2 ? rail : width - rail;
            if (!index) d = `M ${x} ${start}`;
            else d += ` L ${x} ${start}`;
            const a = { x, y: start };
            appendPoint(a);
            const bend = x;
            const endBend = nextX;
            const middleY = (start + top) / 2;
            d += ` C ${bend} ${middleY}, ${endBend} ${middleY}, ${nextX} ${top}`;
            flattenCurve(a, { x: bend, y: middleY }, { x: endBend, y: middleY }, { x: nextX, y: top });
            d += ` L ${nextX} ${top + height}`;
            appendPoint({ x: nextX, y: top + height });
            x = nextX;
        });
        svg.setAttribute('viewBox', `0 0 ${width} ${bounds.height}`);
        track.setAttribute('d', d);
        fill.setAttribute('d', d);
        dirty = false;
    };

    const locate = reader => {
        if (reader <= points[0].y) return points[0];
        const end = points[points.length - 1];
        if (reader >= end.y) return end;
        let low = 0;
        let high = points.length - 1;
        while (high - low > 1) {
            const middle = (low + high) >>> 1;
            if (points[middle].y < reader) low = middle;
            else high = middle;
        }
        const a = points[low], b = points[high];
        const fraction = b.y > a.y ? (reader - a.y) / (b.y - a.y) : 1;
        return { x: a.x + (b.x - a.x) * fraction, y: reader,
            distance: a.distance + (b.distance - a.distance) * fraction };
    };

    const draw = () => {
        frame = undefined;
        if (!enabled || document.hidden || printing) return;
        if (dirty) measure();
        if (!length || points.length < 2) return;
        const scroll = window.scrollY;
        const point = motion.matches || scroll >= lastScroll ? points[points.length - 1] : locate(scroll + viewport * .65 - origin);
        const portion = Math.max(0, Math.min(1, point.distance / length));
        const offset = (1 - portion).toFixed(6);
        const opacity = motion.matches || portion === 0 ? '0' : '1';
        if (offset !== previousOffset) {
            fill.style.strokeDashoffset = offset;
            previousOffset = offset;
        }
        if (opacity !== previousOpacity) {
            head.style.opacity = opacity;
            previousOpacity = opacity;
        }
        if (!motion.matches && portion > 0) {
            const x = point.x.toFixed(2), y = point.y.toFixed(2);
            if (x !== previousX) { head.setAttribute('cx', x); previousX = x; }
            if (y !== previousY) { head.setAttribute('cy', y); previousY = y; }
        }
    };
    const schedule = () => {
        if (enabled && frame === undefined && !document.hidden && !printing) frame = window.requestAnimationFrame(draw);
    };
    const invalidate = () => {
        if (enabled !== desktop.matches) {
            enabled = desktop.matches;
            root.classList.toggle('has-scroll-chain', enabled);
            layer.hidden = !enabled;
        }
        dirty = true;
        schedule();
    };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', invalidate, { passive: true });
    if (window.visualViewport) window.visualViewport.addEventListener('resize', invalidate, { passive: true });
    window.addEventListener('load', invalidate);
    window.addEventListener('pageshow', invalidate);
    document.addEventListener('visibilitychange', schedule);
    document.addEventListener('toggle', invalidate, true);
    if (document.fonts) document.fonts.ready.then(invalidate);
    if (motion.addEventListener) motion.addEventListener('change', schedule);
    if (desktop.addEventListener) desktop.addEventListener('change', invalidate);
    if ('ResizeObserver' in window) new window.ResizeObserver(invalidate).observe(layer.parentElement);
    window.addEventListener('beforeprint', () => { printing = true; });
    window.addEventListener('afterprint', () => { printing = false; invalidate(); });
    invalidate();
})();
