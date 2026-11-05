const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/js/bio-share.js'), 'utf8');

function setup({ width = 240, total = 657, reduced = true } = {}) {
  function element(extra = {}) {
    return { hidden: false, events: {}, addEventListener(name, fn) { this.events[name] = fn; }, ...extra };
  }
  const previous = element();
  const next = element();
  const opener = element();
  const status = element();
  const labels = ['Copiar link', 'Copiar'].map(textContent => ({ textContent }));
  const copyButtons = labels.map(label => element({ querySelector: () => label }));
  const calls = [];
  const networks = element({
    scrollLeft: 0, clientWidth: width, scrollWidth: total,
    querySelector: () => ({ offsetWidth: 76 }),
    scrollTo(options) {
      calls.push(options);
      if (options.behavior === 'instant') this.scrollLeft = options.left;
    },
  });
  const selectors = {
    '.share-scroll-prev': previous, '.share-scroll-next': next,
    '.share-networks': networks, '.share-status': status, '#share-link': {},
    '.share-close': element(), '[data-native-share]': element(),
  };
  const dialog = element({
    dataset: { shareUrl: 'https://knnparaisopolis.com.br/bio' },
    showModal() {},
    querySelector: selector => selectors[selector],
    querySelectorAll: selector => selector === '[data-copy-link]' ? copyButtons : [],
  });
  const windowEvents = {};
  const window = {
    addEventListener(name, callback) { windowEvents[name] = callback; },
    getComputedStyle: () => ({ columnGap: '7px' }),
    matchMedia: () => ({ matches: reduced }),
  };
  const document = {
    getElementById: () => dialog, querySelector: () => opener,
    documentElement: { classList: { add() {}, remove() {} } },
  };
  vm.runInNewContext(source, { document, window, navigator: {}, encodeURIComponent });
  opener.events.click();
  return { networks, previous, next, opener, calls, windowEvents };
}

test('arrows navigate both directions and disable only at the corresponding limit', () => {
  const { previous, next, networks } = setup();
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);
  next.events.click();
  assert.equal(networks.scrollLeft, 166);
  assert.equal(previous.disabled, false);
  next.events.click();
  next.events.click();
  assert.equal(networks.scrollLeft, 417);
  assert.equal(next.disabled, true);
  assert.equal(previous.hidden, false);
  previous.events.click();
  assert.equal(networks.scrollLeft, 251);
  previous.events.click();
  previous.events.click();
  assert.equal(networks.scrollLeft, 0);
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);
});

test('quick clicks accumulate during smooth scrolling, including reversing direction', () => {
  const { next, previous, calls, networks } = setup({ reduced: false });
  next.events.click();
  next.events.click();
  assert.equal(calls.at(-1).left, 332);
  assert.equal(calls.at(-1).behavior, 'smooth');
  previous.events.click();
  assert.equal(calls.at(-1).left, 166);
  networks.scrollLeft = 166;
  networks.events.scroll();
  previous.events.click();
  assert.equal(calls.at(-1).left, 0);
});

test('reopening resets the position immediately after an unfinished animation', () => {
  const { next, calls, opener, networks, previous } = setup({ reduced: false });
  next.events.click();
  networks.scrollLeft = 80;
  opener.events.click();
  assert.equal(networks.scrollLeft, 0);
  assert.equal(calls.at(-1).behavior, 'instant');
  assert.equal(previous.disabled, true);
  next.events.click();
  assert.equal(calls.at(-1).left, 166);
});

test('manual scrolling clears the previous animation target', () => {
  const { next, calls, networks } = setup({ reduced: false });
  next.events.click();
  networks.events.pointerdown();
  networks.scrollLeft = 50;
  next.events.click();
  assert.equal(calls.at(-1).left, 216);
});

test('arrows disappear when all options fit and return after a resize', () => {
  const { previous, next, networks, windowEvents } = setup({ width: 700 });
  assert.equal(previous.hidden, true);
  assert.equal(next.hidden, true);
  networks.clientWidth = 240;
  windowEvents.resize();
  assert.equal(previous.hidden, false);
  assert.equal(next.hidden, false);
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);
});
