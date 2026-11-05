const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/js/landing-effects.js'), 'utf8');

function target(id = '') {
    const classes = new Set();
    const attributes = new Map();
    const style = { setProperty(name, value) { this[name] = value; }, removeProperty(name) { delete this[name]; } };
    return { id, classes, attributes, style, dataset: {},
        setAttribute: (name, value) => attributes.set(name, value), removeAttribute: name => attributes.delete(name),
        classList: { add: name => classes.add(name), remove: name => classes.delete(name),
            toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name) },
        contains: () => false, querySelectorAll: () => [], matches: () => true };
}

function run({ targets = [], timers = [], reduced = false, supportsObserver = true, scrolling = false } = {}) {
    const state = { now: Date.parse('2026-11-30T23:59:58-03:00'), cleared: [], intervals: [], unobserved: [], frames: [] };
    const events = {};
    const windowEvents = {};
    const listen = (map, event, callback) => {
        const previous = map[event];
        map[event] = previous ? (...args) => { previous(...args); callback(...args); } : callback;
    };
    const motion = { matches: reduced, addEventListener: (event, callback) => { state.motionChanged = callback; } };
    const window = {
        location: { hash: '' }, matchMedia: () => motion,
        innerHeight: 800, innerWidth: 1200, scrollY: 0,
        requestAnimationFrame: callback => { state.frames.push(callback); return state.frames.length; },
        addEventListener: (event, callback) => listen(windowEvents, event, callback),
        setInterval: callback => { state.intervals.push(callback); return state.intervals.length; },
        clearInterval: id => { state.cleared.push(id); },
    };
    if (supportsObserver) window.IntersectionObserver = class {
        constructor(callback) { state.intersect = callback; }
        observe() {}
        unobserve(element) { state.unobserved.push(element); }
        disconnect() { state.disconnected = true; }
    };
    const root = { ...target('root'), scrollHeight: 4000 };
    const header = { ...target('header'), getBoundingClientRect: () => ({ height: 80 }) };
    const progress = { hidden: true };
    const fill = target('progress');
    const sections = ['inicio', 'metodo', 'cursos', 'unidade'].map((id, index) => ({
        ...target(id), getBoundingClientRect: () => ({ top: index * 1000 - window.scrollY, height: 1000 }),
    }));
    const links = sections.map((section, index) => ({ ...target(), hash: `#${section.id}`, offsetLeft: index * 90, offsetWidth: 80 }));
    const nav = { querySelectorAll: () => links, scrollWidth: 0, clientWidth: 500, scrollLeft: 0, offsetLeft: 0,
        scrollTo: options => { nav.scrollLeft = options.left; } };
    const layer = { ...target('layer'), dataset: { parallax: '.1' },
        getBoundingClientRect: () => ({ top: 500 - window.scrollY + Number(layer.dataset.parallaxOffset || 0), height: 400 }) };
    const selectors = { '[data-scroll-header]': header, '[data-scroll-progress]': progress,
        '[data-scroll-progress-fill]': fill, '[data-scroll-nav]': nav };
    const document = {
        hidden: false, activeElement: {},
        documentElement: root, body: target('body'),
        querySelector: selector => scrolling ? selectors[selector] || null : null,
        querySelectorAll: selector => ({ '[data-reveal]': targets, '[data-campaign-timing]': timers,
            '[data-parallax]': scrolling ? [layer] : [] }[selector] || []),
        addEventListener: (event, callback) => listen(events, event, callback),
        getElementById: id => [...targets, ...sections].find(element => element.id === id),
    };
    vm.runInNewContext(script, { window, document, Date: { now: () => state.now, parse: Date.parse } });
    const flush = () => state.frames.splice(0).forEach(callback => callback());
    return { state, events, document, windowEvents, window, root, header, progress, fill, links, nav, layer, flush };
}

test('cards reveal once on intersection, and keyboard focus reveals a pending card', () => {
    const cards = [target('offer'), target('community')];
    const { state, events } = run({ targets: cards });
    assert.ok(cards[0].classes.has('is-pending'));
    state.intersect([{ target: cards[0], isIntersecting: false }]);
    assert.ok(cards[0].classes.has('is-pending'));
    state.intersect([{ target: cards[0], isIntersecting: true }]);
    assert.ok(!cards[0].classes.has('is-pending'));
    assert.ok(cards[0].classes.has('is-visible'));
    events.focusin({ target: { closest: () => cards[1] } });
    assert.ok(!cards[1].classes.has('is-pending'));
    assert.equal(state.unobserved.length, 2);
});

test('reduced motion and missing observer keep content visible; changing the preference reveals everything', () => {
    for (const options of [{ reduced: true }, { supportsObserver: false }]) {
        const card = target();
        run({ targets: [card], ...options });
        assert.ok(!card.classes.has('is-pending'));
    }
    const card = target();
    const { state } = run({ targets: [card] });
    state.motionChanged({ matches: true });
    assert.ok(!card.classes.has('is-pending'));
    assert.ok(state.disconnected);
});

test('anchor navigation reveals its destination before scrolling', () => {
    const section = target('comunidades');
    const { events } = run({ targets: [section] });
    events.click({ target: { closest: () => ({ hash: '#comunidades' }) } });
    assert.ok(!section.classes.has('is-pending'));
});

test('anchor navigation reveals nested content before a long smooth scroll', () => {
    const child = target();
    const section = target('metodo');
    section.querySelectorAll = () => [child];
    const { events } = run({ targets: [section, child] });
    assert.ok(child.classes.has('is-pending'));
    events.click({ target: { closest: () => ({ hash: '#metodo' }) } });
    assert.ok(!child.classes.has('is-pending'));
    assert.ok(child.classes.has('is-visible'));
});

test('real deadline expires without resetting, progress clamps, and hidden tabs pause updates', () => {
    const parts = Object.fromEntries(['days', 'hours', 'minutes', 'seconds'].map(part => [part, {}]));
    const countdown = { hidden: true };
    const status = {};
    const progress = {};
    const label = {};
    const timer = {
        dataset: { start: '2026-11-01T00:00:00-03:00', end: '2026-12-01T00:00:00-03:00' },
        querySelector: selector => ({ '[data-countdown]': countdown, '[data-timing-status]': status,
            '[data-campaign-progress]': progress, '[data-progress-label]': label }[selector]
            || parts[selector.match(/data-time="(.*?)"/)?.[1]]),
    };
    const { state, events, document } = run({ timers: [timer] });
    assert.equal(countdown.hidden, false);
    assert.equal(parts.seconds.textContent, '02');
    assert.equal(state.intervals.length, 1);
    document.hidden = true;
    events.visibilitychange();
    assert.equal(state.cleared.length, 1);
    state.now += 4000;
    document.hidden = false;
    events.visibilitychange();
    assert.equal(countdown.hidden, true);
    assert.match(status.textContent, /Período encerrado/);
    assert.equal(progress.value, 100);
    assert.equal(state.intervals.length, 1);
});

test('page progress and section navigation update once per frame without changing the URL', () => {
    const view = run({ scrolling: true });
    view.flush();
    assert.equal(view.progress.hidden, false);
    assert.equal(view.fill.style.transform, 'scaleX(0)');
    assert.equal(view.links[0].attributes.get('aria-current'), 'location');
    view.window.scrollY = 1250;
    for (let i = 0; i < 12; i++) view.windowEvents.scroll();
    assert.equal(view.state.frames.length, 1);
    view.flush();
    assert.equal(view.fill.style.transform, 'scaleX(0.390625)');
    assert.equal(view.links[1].attributes.get('aria-current'), 'location');
    assert.equal(view.links[0].attributes.has('aria-current'), false);
    assert.ok(view.header.classes.has('is-scrolled'));
    assert.equal(view.window.location.hash, '');
    view.window.scrollY = 5000;
    view.windowEvents.scroll();
    view.flush();
    assert.equal(view.fill.style.transform, 'scaleX(1)');
});

test('parallax is bounded and resets on mobile and on a reduced-motion preference change', () => {
    const view = run({ scrolling: true });
    view.flush();
    assert.equal(view.layer.style.transform, 'translate3d(0, -30.00px, 0)');
    view.window.scrollY = 1000;
    view.windowEvents.scroll();
    view.flush();
    assert.equal(view.layer.style.transform, 'translate3d(0, 48.00px, 0)');
    view.state.motionChanged({ matches: true });
    view.flush();
    assert.equal(view.layer.style.transform, undefined);
    assert.equal(view.layer.dataset.parallaxOffset, '0');
    view.state.motionChanged({ matches: false });
    view.flush();
    assert.equal(view.layer.style.transform, 'translate3d(0, 48.00px, 0)');
    view.window.innerWidth = 390;
    view.windowEvents.resize();
    view.flush();
    assert.equal(view.layer.style.transform, undefined);
    assert.equal(view.layer.dataset.parallaxOffset, '0');
});

test('layout changes recalculate reading progress and hidden tabs do not queue scroll frames', () => {
    const view = run({ scrolling: true });
    view.flush();
    view.document.hidden = true;
    view.window.scrollY = 1600;
    view.windowEvents.scroll();
    assert.equal(view.state.frames.length, 0);
    view.root.scrollHeight = 4800;
    view.document.hidden = false;
    view.events.visibilitychange();
    view.flush();
    assert.equal(view.fill.style.transform, 'scaleX(0.4)');
    view.root.scrollHeight = 4000;
    view.events.toggle();
    view.flush();
    assert.equal(view.fill.style.transform, 'scaleX(0.5)');
});

test('mobile section tracking scrolls only the navigation strip to keep the active item visible', () => {
    const view = run({ scrolling: true });
    view.window.innerWidth = 390;
    view.nav.clientWidth = 150;
    view.nav.scrollWidth = 500;
    view.window.scrollY = 2200;
    view.flush();
    assert.equal(view.links[2].attributes.get('aria-current'), 'location');
    assert.equal(view.nav.scrollLeft, 145);
    assert.equal(view.window.scrollY, 2200);
});
