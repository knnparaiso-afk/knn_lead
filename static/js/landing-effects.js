/* Sem dependências. Conteúdo visível sem JavaScript e com movimento reduzido. */
(() => {
    'use strict';

    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reducedMotion = motion.matches;
    let refreshScrollEffects = () => {};
    let printing = false;
    const header = document.querySelector('[data-scroll-header]');
    const scrollLinkedReveals = Boolean(header && window.requestAnimationFrame);
    const targets = Array.from(document.querySelectorAll('[data-reveal]'));
    const revealItems = scrollLinkedReveals ? targets.map(element => {
        element.classList.add('is-scroll-linked');
        return { element, offset: 0 };
    }) : [];
    let observer;
    const reveal = element => {
        if (scrollLinkedReveals) {
            element.style.opacity = '1';
            element.style.removeProperty('transform');
            const item = revealItems.find(item => item.element === element);
            if (item) item.offset = 0;
            refreshScrollEffects();
        }
        element.classList.remove('is-pending');
        element.classList.add('is-visible');
        if (observer) observer.unobserve(element);
    };
    const revealAll = () => {
        if (observer) observer.disconnect();
        targets.forEach(element => {
            element.style.removeProperty('opacity');
            element.style.removeProperty('transform');
            reveal(element);
        });
    };

    if (!scrollLinkedReveals && !motion.matches && 'IntersectionObserver' in window) {
        try {
            observer = new window.IntersectionObserver(entries => {
                for (const entry of entries) if (entry.isIntersecting) reveal(entry.target);
            }, {
                threshold: 0,
                // Dispara depois que parte do bloco já entrou na tela, inclusive
                // em cartões muito altos no celular (sem exigir uma razão mínima).
                rootMargin: `0px 0px -${Math.min(120, Math.max(56, Math.round(window.innerHeight * .14)))}px 0px`,
            });
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
            // Na landing, o destino anima ao chegar à tela, não durante o salto.
            if (scrollLinkedReveals) { refreshScrollEffects(); return; }
            if (section.matches('[data-reveal]')) reveal(section);
            section.querySelectorAll('[data-reveal]').forEach(reveal);
        }
    });
    if (motion.addEventListener) motion.addEventListener('change', event => {
        reducedMotion = event.matches;
        if (reducedMotion && !scrollLinkedReveals) revealAll();
        refreshScrollEffects();
    });
    window.addEventListener('beforeprint', () => { printing = true; revealAll(); });
    window.addEventListener('afterprint', () => { printing = false; refreshScrollEffects(); });

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

    // Um único frame por atualização, sem animação contínua quando a página para.
    if (!header || !window.requestAnimationFrame) return;
    const root = document.documentElement;
    const progress = document.querySelector('[data-scroll-progress]');
    const progressFill = document.querySelector('[data-scroll-progress-fill]');
    const nav = document.querySelector('[data-scroll-nav]');
    const sections = nav ? Array.from(nav.querySelectorAll('a[href^="#"]')).map(link => ({
        link, section: document.getElementById(link.hash.slice(1)),
    })).filter(item => item.section) : [];
    const layers = Array.from(document.querySelectorAll('[data-parallax]')).map(element => ({
        element, speed: Math.max(-.2, Math.min(.2, Number(element.dataset.parallax) || 0)),
    }));
    let frame;
    let activeLink;
    let headerHeight = 0;
    root.classList.add('has-scroll-effects');
    root.dataset.revealEngine = 'scroll-v2';
    if (progress) progress.hidden = false;

    const updateScrollEffects = () => {
        frame = undefined;
        if (document.hidden || printing) return;
        const viewport = window.innerHeight;
        const scroll = Math.max(0, window.scrollY);
        const height = header.getBoundingClientRect().height;
        if (height !== headerHeight) {
            headerHeight = height;
            root.style.setProperty('--header-height', `${Math.ceil(height)}px`);
        }
        const distance = Math.max(0, root.scrollHeight - viewport);
        if (progressFill) progressFill.style.transform = `scaleX(${distance ? Math.min(1, scroll / distance) : 0})`;
        header.classList.toggle('is-scrolled', scroll > 24);

        // Transparência ligada à posição real, sem depender de keyframes,
        // duração do Android, IntersectionObserver ou uma entrada única.
        // Leia as posições antes de gravar estilos para não alternar layout/write.
        const reveals = revealItems.map(item => {
            const bounds = item.element.getBoundingClientRect();
            const top = bounds.top - item.offset;
            const span = Math.max(64, Math.min(180, bounds.height * .28));
            const entering = (viewport - 48 - top) / span;
            const leaving = (top + bounds.height - height - 16) / span;
            const progress = reducedMotion || item.element.contains(document.activeElement) ? 1 :
                Math.max(0, Math.min(1, entering, leaving));
            return { item, progress, offset: reducedMotion ? 0 : (1 - progress) * 24 };
        });
        for (const { item, progress, offset } of reveals) {
            item.element.style.opacity = progress.toFixed(3);
            if (offset) item.element.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0)`;
            else item.element.style.removeProperty('transform');
            item.offset = offset;
            item.element.classList.toggle('is-pending', progress === 0);
            item.element.classList.toggle('is-visible', progress > 0);
        }

        const readingLine = height + Math.max(24, (viewport - height) * .22);
        let current;
        for (const item of sections) if (item.section.getBoundingClientRect().top <= readingLine) current = item;
        if (current && current.link !== activeLink) {
            for (const item of sections) {
                item.link.classList.toggle('is-active', item === current);
                if (item === current) item.link.setAttribute('aria-current', 'location');
                else item.link.removeAttribute('aria-current');
            }
            activeLink = current.link;
            // Desloca apenas a faixa horizontal do menu no celular, nunca a página.
            if (nav.scrollWidth > nav.clientWidth && nav.scrollTo) {
                const left = activeLink.offsetLeft - nav.offsetLeft;
                if (left < nav.scrollLeft || left + activeLink.offsetWidth > nav.scrollLeft + nav.clientWidth) {
                    nav.scrollTo({ left: Math.max(0, left - (nav.clientWidth - activeLink.offsetWidth) / 2), behavior: 'instant' });
                }
            }
        }

        for (const { element, speed } of layers) {
            if (reducedMotion) {
                element.style.removeProperty('transform');
                element.dataset.parallaxOffset = '0';
                continue;
            }
            const bounds = element.getBoundingClientRect();
            // Usa a posição original para que o transform não realimente o cálculo.
            const originalTop = bounds.top - (Number(element.dataset.parallaxOffset) || 0);
            const mobile = window.innerWidth < 860;
            const limit = mobile ? 18 : 48;
            const intensity = mobile ? .6 : 1;
            const offset = Math.max(-limit, Math.min(limit, (viewport / 2 - originalTop - bounds.height / 2) * speed * intensity));
            element.dataset.parallaxOffset = String(offset);
            element.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0)`;
        }
    };
    const scheduleScrollEffects = () => {
        if (frame === undefined && !document.hidden) frame = window.requestAnimationFrame(updateScrollEffects);
    };
    refreshScrollEffects = scheduleScrollEffects;
    window.addEventListener('scroll', scheduleScrollEffects, { passive: true });
    window.addEventListener('resize', scheduleScrollEffects, { passive: true });
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', scheduleScrollEffects, { passive: true });
        window.visualViewport.addEventListener('scroll', scheduleScrollEffects, { passive: true });
    }
    window.addEventListener('load', scheduleScrollEffects);
    window.addEventListener('pageshow', scheduleScrollEffects);
    document.addEventListener('visibilitychange', scheduleScrollEffects);
    document.addEventListener('toggle', scheduleScrollEffects, true);
    if ('ResizeObserver' in window) {
        const layoutObserver = new window.ResizeObserver(scheduleScrollEffects);
        layoutObserver.observe(document.body);
        layoutObserver.observe(header);
    }
    scheduleScrollEffects();
})();
