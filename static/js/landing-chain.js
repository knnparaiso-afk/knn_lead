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
    if (!stops.length || !fill.getTotalLength || !fill.getPointAtLength) return;
    const root = document.documentElement;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let dirty = true;
    let frame;
    let length = 0;
    let origin = 0;
    let printing = false;

    root.classList.add('has-scroll-chain');
    layer.hidden = false;

    const measure = () => {
        const bounds = layer.getBoundingClientRect();
        const width = bounds.width;
        if (!width || !bounds.height) return;
        origin = bounds.top + window.scrollY;
        const mobile = width < 760;
        const rail = mobile ? 10 : Math.max(18, (width - 1240) / 2 + 18);
        let x = width / 2;
        let d = '';
        stops.forEach((stop, index) => {
            const rect = stop.getBoundingClientRect();
            const top = rect.top - bounds.top;
            const gap = stop.previousElementSibling.getBoundingClientRect().height;
            const start = top - gap;
            const nextX = mobile ? rail : (index % 2 ? rail : width - rail);
            if (!index) d = `M ${x} ${start}`;
            else d += ` L ${x} ${start}`;
            const bend = mobile ? Math.min(width * .42, 160) : x;
            const endBend = mobile ? bend : nextX;
            d += ` C ${bend} ${start + gap * .5}, ${endBend} ${start + gap * .5}, ${nextX} ${top}`;
            d += ` L ${nextX} ${top + rect.height}`;
            x = nextX;
        });
        svg.setAttribute('viewBox', `0 0 ${width} ${bounds.height}`);
        track.setAttribute('d', d);
        fill.setAttribute('d', d);
        length = fill.getTotalLength();
        dirty = false;
    };

    const draw = () => {
        frame = undefined;
        if (document.hidden || printing) return;
        if (dirty) measure();
        if (!length) return;
        const reader = window.scrollY + window.innerHeight * .65 - origin;
        const last = root.scrollHeight - window.innerHeight - 1;
        let reached;
        if (motion.matches || window.scrollY >= last) reached = length;
        else {
            // O traçado sempre desce: encontra o ponto na altura da leitura,
            // inclusive nas curvas e em seções de tamanhos diferentes.
            let low = 0;
            let high = length;
            for (let i = 0; i < 14; i++) {
                const middle = (low + high) / 2;
                if (fill.getPointAtLength(middle).y < reader) low = middle;
                else high = middle;
            }
            reached = reader <= fill.getPointAtLength(0).y ? 0 : (low + high) / 2;
        }
        const portion = Math.max(0, Math.min(1, reached / length));
        fill.style.strokeDashoffset = String(1 - portion);
        head.style.opacity = motion.matches || portion === 0 ? '0' : '1';
        if (!motion.matches && portion > 0) {
            const point = fill.getPointAtLength(reached);
            head.setAttribute('cx', point.x.toFixed(2));
            head.setAttribute('cy', point.y.toFixed(2));
        }
    };
    const schedule = () => {
        if (frame === undefined && !document.hidden && !printing) frame = window.requestAnimationFrame(draw);
    };
    const invalidate = () => { dirty = true; schedule(); };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', invalidate, { passive: true });
    window.addEventListener('load', invalidate);
    window.addEventListener('pageshow', invalidate);
    document.addEventListener('visibilitychange', schedule);
    document.addEventListener('toggle', invalidate, true);
    if (document.fonts) document.fonts.ready.then(invalidate);
    if (motion.addEventListener) motion.addEventListener('change', schedule);
    if ('ResizeObserver' in window) new window.ResizeObserver(invalidate).observe(layer.parentElement);
    window.addEventListener('beforeprint', () => { printing = true; });
    window.addEventListener('afterprint', () => { printing = false; invalidate(); });
    schedule();
})();
