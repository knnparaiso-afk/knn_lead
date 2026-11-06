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
        set scrollHeight(value) { scrollHeight = value; }, classList: { add() {} } };
    const motion = { matches: reduced, addEventListener(event, cb) { motion.change = cb; } };
    const window = { innerHeight: 800, scrollY: 0, width,
        requestAnimationFrame(cb) { frames.push(cb); return frames.length; },
        matchMedia: () => motion,
        addEventListener(event, cb) { windowEvents[event] = cb; },
        ResizeObserver: class { constructor(cb) { window.resizeObserved = cb; } observe() {} },
    };
    const layer = { hidden: true, parentElement: {},
        getBoundingClientRect: () => { measures++; layoutReads++; return { width: window.width, height: 4000, top: 100 - window.scrollY }; },
        querySelector: s => ({ svg, '[data-chain-track]': track, '[data-chain-fill]': fill, '[data-chain-head]': head }[s]),
    };
    const stops = [900, 1900, 2900].map(top => ({
        getBoundingClientRect: () => { layoutReads++; return { top: top - window.scrollY, height: 800 }; },
        previousElementSibling: { getBoundingClientRect: () => { layoutReads++; return { height: 80 }; } },
    }));
    const document = { hidden: false, documentElement: root,
        querySelector: () => layer, querySelectorAll: () => stops,
        addEventListener(event, cb) { events[event] = cb; },
    };
    vm.runInNewContext(script, { window, document });
    const flush = () => frames.splice(0).forEach(cb => cb());
    return { window, document, root, layer, svg, track, fill, head, motion,
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

test('resize rebuilds the chain and mobile vertical rails stay at the margin', () => {
    const v = view(); v.flush();
    const desktop = v.fill.attrs.d;
    v.window.width = 390;
    v.windowEvents.resize(); v.flush();
    assert.notEqual(v.fill.attrs.d, desktop);
    const rails = [...v.fill.attrs.d.matchAll(/ L ([\d.]+) /g)].map(m => Number(m[1]));
    assert.ok(rails.length > 0 && rails.every(x => x < 22));
    assert.equal(v.measures(), 2);
    v.window.resizeObserved(); v.flush();
    assert.equal(v.measures(), 3);
});

test('reduced motion keeps a static complete chain and hides the moving point', () => {
    const v = view({ reduced: true }); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 0);
    assert.equal(v.head.style.opacity, '0');
    v.motion.matches = false; v.motion.change(); v.flush();
    assert.equal(Number(v.fill.style.strokeDashoffset), 1);
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
    const v = view({ width: 390 }); v.flush();
    v.window.scrollY = 1500;
    v.windowEvents.scroll(); v.flush();
    assert.equal(Number(v.head.attrs.cx), 10);
    assert.equal(Number(v.head.attrs.cy), 1920);
    v.window.innerHeight = 600;
    v.windowEvents.resize(); v.flush();
    assert.equal(Number(v.head.attrs.cy), 1790);
});
