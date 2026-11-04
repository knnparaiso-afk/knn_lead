/* Sem dependências. A primeira tela e o formulário permanecem visíveis. */
(() => {
    'use strict';

    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const targets = Array.from(document.querySelectorAll('[data-reveal]'));
    let observer;
    const reveal = element => {
        element.classList.remove('is-pending');
        element.classList.add('is-visible');
        if (observer) observer.unobserve(element);
    };
    const revealAll = () => {
        if (observer) observer.disconnect();
        targets.forEach(reveal);
    };

    if (!motion.matches && 'IntersectionObserver' in window) {
        try {
            observer = new window.IntersectionObserver(entries => {
                for (const entry of entries) if (entry.isIntersecting) reveal(entry.target);
            }, { threshold: .08, rootMargin: '0px 0px -24px 0px' });
            for (const element of targets) {
                // Nunca oculta um destino de âncora ou controle que já tem foco.
                if ((element.id && window.location.hash === `#${element.id}`) || element.contains(document.activeElement)) continue;
                observer.observe(element);
                element.classList.add('is-pending');
            }
        } catch {
            revealAll();
        }
    }
    document.addEventListener('focusin', event => {
        const section = event.target.closest('[data-reveal].is-pending');
        if (section) reveal(section);
    });
    document.addEventListener('click', event => {
        const anchor = event.target.closest('a[href^="#"]');
        const section = anchor && document.getElementById(anchor.hash.slice(1));
        if (section) {
            if (section.matches('[data-reveal]')) reveal(section);
        }
    });
    if (motion.addEventListener) motion.addEventListener('change', event => { if (event.matches) revealAll(); });
    window.addEventListener('beforeprint', revealAll);

    const timers = Array.from(document.querySelectorAll('[data-campaign-timing]'));
    let interval;
    const updateTimers = () => {
        const now = Date.now();
        let running = false;
        for (const element of timers) {
            const end = Date.parse(element.dataset.end);
            if (!Number.isFinite(end)) continue;
            const remaining = Math.max(0, Math.ceil((end - now) / 1000));
            const countdown = element.querySelector('[data-countdown]');
            const status = element.querySelector('[data-timing-status]');
            if (remaining > 0) {
                const values = {
                    days: Math.floor(remaining / 86400), hours: Math.floor(remaining / 3600) % 24,
                    minutes: Math.floor(remaining / 60) % 60, seconds: remaining % 60,
                };
                for (const [part, value] of Object.entries(values)) {
                    const label = element.querySelector(`[data-time="${part}"]`);
                    const text = String(value).padStart(2, '0');
                    if (label.textContent !== text) label.textContent = text;
                }
                countdown.hidden = false;
                status.textContent = '';
                running = true;
            } else {
                countdown.hidden = true;
                status.textContent = 'Período encerrado. Consulte a unidade sobre novas oportunidades.';
            }
            const start = Date.parse(element.dataset.start);
            const progress = element.querySelector('[data-campaign-progress]');
            if (progress && Number.isFinite(start) && end > start) {
                const percentage = Math.floor(Math.max(0, Math.min(100, (now - start) / (end - start) * 100)));
                progress.value = percentage;
                element.querySelector('[data-progress-label]').textContent = `${percentage}% transcorrido`;
            }
        }
        if (!running && interval) { window.clearInterval(interval); interval = undefined; }
        return running;
    };
    const resumeTimers = () => {
        if (!document.hidden && updateTimers() && !interval) interval = window.setInterval(updateTimers, 1000);
    };
    if (timers.length) {
        resumeTimers();
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) { window.clearInterval(interval); interval = undefined; }
            else resumeTimers();
        });
        window.addEventListener('pageshow', resumeTimers);
    }
})();
