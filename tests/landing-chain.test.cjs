const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../static/js/landing-chain.js'), 'utf8');

function view({ width = 1200, reduced = false } = {}) {
    const frames = [];
    const events = {};
    const windowEvents = {};
    let writes = 0;
    let layoutReads = 0;
    const element = () => ({ style: new Proxy({}, { set(obj, key, value) { writes++; obj[key] = value; return true; } }),
        attrs: {}, setAttribute(k, v) { writes++; this.attrs[k] = v; } });
    const svg = element(), track = element(), fill = element(), head = element();
    let measures = 0;
    fill.getTotalLength = () => { throw new Error('Native SVG measurement must not run'); };
    fill.getPointAtLength = () => { throw new Error('Native SVG position lookup must not run'); };
    let scrollHeight = 4200;
    const root = { get scrollHeight() { layoutReads++; return scrollHeight; },
        set scrollHeight(value) { scrollHeight = value; }, classList: { toggle() {} } };
    const motion = { matches: reduced, addEventListener(event, cb) { motion.change = cb; } };
    const desktop = { matches: width > 760, addEventListener(event, cb) { desktop.change = cb; } };
    const window = { innerHeight: 800, scrollY: 0, width, wrapWidth: 1240,
        requestAnimationFrame(cb) { frames.push(cb); return frames.length; },
        matchMedia: query => query.includes('min-width') ? desktop : motion,
        addEventListener(event, cb) { windowEvents[event] = cb; },
        ResizeObserver: class { constructor(cb) { window.resizeObserved = cb; } observe() {} },
    };
    const layer = { hidden: true, parentElement: {},
        getBoundingClientRect: () => { measures++; layoutReads++; return { width: window.width, height: 4000, top: 100 - window.scrollY }; },
        querySelector: s => ({ svg, '[data-chain-track]': track, '[data-chain-fill]': fill, '[data-chain-head]': head }[s]),
    };
    const heroGrid = { getBoundingClientRect() { layoutReads++; return { width: Math.min(window.width, window.wrapWidth) }; } };
    const stops = [900, 1900, 2900].map(top => ({
        getBoundingClientRect: () => { layoutReads++; return { top: top - window.scrollY, height: 800 }; },
        previousElementSibling: { getBoundingClientRect: () => { layoutReads++; return { height: 80 }; } },
    }));
    const document = { hidden: false, documentElement: root,
        querySelector: selector => selector === '.hero-grid' ? heroGrid : layer, querySelectorAll: () => stops,
        addEventListener(event, cb) { events[event] = cb; },
    };
    vm.runInNewContext(script, { window, document });
    const flush = () => frames.splice(0).forEach(cb => cb());
    return { window, document, root, layer, svg, track, fill, head, motion, desktop,
        events, windowEvents, frames, flush, measures: () => measures,
        layoutReads: () => layoutReads, writes: () => writes };
}

test('chain follows scrolling in both directions, finishes at page end and reuses geometry', () => {
    const v = view();
    v.flush();
    assert.equal(v.layer.hidden, false);
    assert.equal(Number(v.fill.style.strokeDashoffset), 1);
    v.window.scrollY = 1500;
    for (let i = 0; i < 10; i++) v.windowEvents.scroll();
    assert.equal(v.frames.length, 1);
    v.flush();
    const middle = Number(v.fill.style.strokeDashoffset);
    assert.ok(middle > 0 && middle < 1);
    assert.equal(v.head.style.opacity, '1');
    v.window.scrollY = 3400;
    v.windowEvents.scroll(); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 0);
    v.window.scrollY = 0;
    v.windowEvents.scroll(); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 1);
    assert.equal(v.measures(), 1);
    assert.equal(v.frames.length, 0);
});

test('resize rebuilds the desktop chain and suspends it on mobile', () => {
    const v = view(); v.flush();
    const desktop = v.fill.attrs.d;
    v.window.width = 1000;
    v.windowEvents.resize(); v.flush();
    assert.notEqual(v.fill.attrs.d, desktop);
    assert.equal(v.measures(), 2);
    v.window.resizeObserved(); v.flush();
    assert.equal(v.measures(), 3);
    v.desktop.matches = false;
    v.desktop.change(); v.flush();
    assert.equal(v.layer.hidden, true);
    v.windowEvents.scroll();
    assert.equal(v.frames.length, 0);
    assert.equal(v.measures(), 3);
    v.desktop.matches = true;
    v.desktop.change(); v.flush();
    assert.equal(v.layer.hidden, false);
    assert.equal(v.measures(), 4);
    const mobile = view({ width: 760 });
    mobile.windowEvents.scroll(); mobile.flush();
    assert.equal(mobile.layer.hidden, true);
    assert.equal(mobile.frames.length, 0);
    assert.equal(mobile.measures(), 0);
});

test('reduced motion keeps a static complete chain and hides the moving point', () => {
    const v = view({ reduced: true }); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 0);
    assert.equal(v.head.style.opacity, '0');
    v.motion.matches = false; v.motion.change(); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 1);
});

test('chain rails follow the measured width of the landing content', () => {
    const v = view({ width: 1520 });
    v.flush();
    assert.match(v.track.attrs.d, /L 1362 1600/);
    v.window.wrapWidth = 1420;
    v.window.resizeObserved(); v.flush();
    assert.match(v.track.attrs.d, /L 1452 1600/);
    assert.match(v.track.attrs.d, /L 68 2600/);
});

test('hidden tabs and printing suspend updates; reopening details recalculates geometry', () => {
    const v = view(); v.flush();
    v.document.hidden = true;
    v.windowEvents.scroll();
    assert.equal(v.frames.length, 0);
    v.document.hidden = false;
    v.events.visibilitychange(); v.flush();
    v.windowEvents.beforeprint(); v.windowEvents.scroll();
    assert.equal(v.frames.length, 0);
    v.windowEvents.afterprint(); v.flush();
    v.events.toggle(); v.flush();
    assert.equal(v.measures(), 3);
});

test('scrolling uses cached geometry and avoids duplicate SVG writes', () => {
    const v = view(); v.flush();
    const reads = v.layoutReads();
    v.window.scrollY = 1500;
    v.windowEvents.scroll(); v.flush();
    assert.equal(v.layoutReads(), reads);
    const writes = v.writes();
    v.windowEvents.scroll(); v.flush();
    assert.equal(v.writes(), writes);
    v.window.scrollY = 1300;
    v.windowEvents.scroll(); v.flush();
    assert.equal(v.layoutReads(), reads);
    assert.ok(v.writes() > writes);
});

test('the moving point follows reader height and a viewport resize refreshes its position', () => {
    const v = view(); v.flush();
    v.window.scrollY = 1500;
    v.windowEvents.scroll(); v.flush();
    assert.equal(Number(v.head.attrs.cx), 18);
    assert.equal(Number(v.head.attrs.cy), 1920);
    v.window.innerHeight = 600;
    v.windowEvents.resize(); v.flush();
    assert.equal(Number(v.head.attrs.cy), 1790);
});
