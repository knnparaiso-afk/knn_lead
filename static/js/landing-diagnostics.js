/* Diagnóstico local e opt-in por URL. Não envia informações ao servidor. */
(() => {
    'use strict';
    const errors = [];
    const panel = document.createElement('details');
    panel.className = 'motion-debug';
    panel.open = true;
    const title = document.createElement('summary');
    title.textContent = 'Diagnóstico de efeitos · toque para recolher';
    const output = document.createElement('textarea');
    output.readOnly = true;
    output.setAttribute('aria-label', 'Diagnóstico para copiar e enviar nesta conversa');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Copiar diagnóstico';
    panel.append(title, output, button);
    document.body.append(panel);

    const refresh = () => {
        const hero = document.querySelector('.hero-copy');
        const style = hero && getComputedStyle(hero);
        output.value = JSON.stringify({
            engine: document.documentElement.dataset.revealEngine || 'não iniciou',
            browser: navigator.userAgent,
            viewport: `${window.innerWidth}x${window.innerHeight}`,
            touchPoints: navigator.maxTouchPoints,
            reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
            intersectionObserver: 'IntersectionObserver' in window,
            effectsJS: document.querySelector('script[src*="landing-effects.js"]')?.getAttribute('src'),
            effectsCSS: document.querySelector('link[href*="landing-effects.css"]')?.getAttribute('href'),
            animatedBlocks: document.querySelectorAll('.is-scroll-linked').length,
            inlineOpacity: hero?.style.opacity,
            opacity: style?.opacity,
            animation: style?.animationName,
            scroll: Math.round(window.scrollY),
            errors,
        }, null, 2);
    };
    window.addEventListener('error', event => { errors.push(event.message); if (errors.length > 5) errors.shift(); refresh(); });
    window.addEventListener('load', refresh);
    window.addEventListener('pageshow', refresh);
    button.addEventListener('click', async () => {
        refresh();
        try {
            await navigator.clipboard.writeText(output.value);
            button.textContent = 'Copiado';
        } catch {
            output.focus();
            output.select();
            button.textContent = 'Selecione e copie o texto acima';
        }
    });
    refresh();
})();
