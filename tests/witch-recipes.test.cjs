const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function gameFixture() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: { display: 'none' }, textContent: '', addEventListener() {} });
    return elements.get(id);
  };
  const timers = [];
  const window = { WITCH_CONFIG: {}, addEventListener() {} };
  const context = vm.createContext({ window, document: { getElementById: element }, setTimeout: callback => timers.push(callback), clearTimeout() {} });
  const source = fs.readFileSync(path.join(__dirname, '../static/js/witch-game.js'), 'utf8');
  vm.runInContext(source.replace(/\}\)\(\);\s*$/, 'window.testGame = { generateDynamicRecipes, GameController };})();'), context);
  return { ...window.testGame, element, timers };
}

test('two recipes have two steps each and four distinct targets', () => {
  const { generateDynamicRecipes } = gameFixture();
  for (let run = 0; run < 100; run++) {
    const recipes = generateDynamicRecipes();
    assert.equal(recipes.length, 2);
    const targets = new Set(recipes.flatMap(recipe => recipe.tasks.map(task => task.target)));
    assert.equal(targets.size, 4);
    recipes.forEach((recipe, index) => {
      assert.equal(recipe.tag, `Receita ${index + 1}/2`);
      assert.equal(recipe.tasks.length, 2);
      recipe.tasks.forEach(task => {
        assert.equal(new Set(task.distractors).size, 2);
        task.distractors.forEach(id => assert.ok(!targets.has(id)));
      });
    });
  }
});

test('the final recipe goes straight to victory with the green reward button', () => {
  const { GameController, element, timers } = gameFixture();
  const game = new GameController({ reactHappy() {} });
  let confirmations = 0;
  game._notifyBackendVictory = () => { confirmations++; };
  game.recipeIdx = 0;
  game.finishRecipe();
  assert.equal(element('screen-victory').style.display, 'none');
  timers.splice(0).forEach(callback => callback());
  assert.equal(element('screen-recipe-done').style.display, 'flex');
  game.recipeIdx = 1;
  game.taskIdx = 2;
  game.score = 400;
  game.finishRecipe();
  assert.equal(element('screen-recipe-done').style.display, 'none');
  assert.equal(element('screen-victory').style.display, 'flex');
  assert.equal(element('victory-final-score').textContent, 400);
  assert.equal(confirmations, 1);
  const template = fs.readFileSync(path.join(__dirname, '../templates/jogo_witchs_potion.html'), 'utf8');
  assert.match(template, /class="btn-witch-glow btn-gold" id="btn-claim-rewards"/);
  const css = fs.readFileSync(path.join(__dirname, '../static/css/witch-game.css'), 'utf8');
  assert.match(css, /\.btn-witch-glow\.btn-gold\s*\{[^}]*#22c55e[^}]*#15803d/);
});
