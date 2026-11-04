const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/js/landing-effects.js'), 'utf8');

function target(id = '') {
    const classes = new Set();
    return { id, classes, classList: { add: name => classes.add(name), remove: name => classes.delete(name) },
        contains: () => false, querySelectorAll: () => [], matches: () => true };
}

function run({ targets = [], timers = [], reduced = false, supportsObserver = true } = {}) {
    const state = { now: Date.parse('2026-11-30T23:59:58-03:00'), cleared: [], intervals: [], unobserved: [] };
    const events = {};
    const windowEvents = {};
    const motion = { matches: reduced, addEventListener: (event, callback) => { state.motionChanged = callback; } };
    const window = {
        location: { hash: '' }, matchMedia: () => motion,
        addEventListener: (event, callback) => { windowEvents[event] = callback; },
        setInterval: callback => { state.intervals.push(callback); return state.intervals.length; },
        clearInterval: id => { state.cleared.push(id); },
    };
    if (supportsObserver) window.IntersectionObserver = class {
        constructor(callback) { state.intersect = callback; }
        observe() {}
        unobserve(element) { state.unobserved.push(element); }
        disconnect() { state.disconnected = true; }
    };
    const document = {
        hidden: false, activeElement: {},
        querySelectorAll: selector => selector === '[data-reveal]' ? targets : timers,
        addEventListener: (event, callback) => { events[event] = callback; },
        getElementById: id => targets.find(element => element.id === id),
    };
    vm.runInNewContext(script, { window, document, Date: { now: () => state.now, parse: Date.parse } });
    return { state, events, document, windowEvents };
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
