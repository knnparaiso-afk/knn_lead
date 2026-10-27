const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../templates/participar.html'), 'utf8');
const script = template.match(/<script>\s*(\(\(\) => \{[\s\S]*?)<\/script>/)[1]
    .replace(/\{\{ url_for\('public.participar', codigo=qr.codigo\)\|tojson \}\}/, '"/participar/TEST"');

test('typing a phone updates the reward and duplicate status without another click', async () => {
    const handlers = {};
    const fields = { span: {}, strong: {}, small: {} };
    const phone = { value: '', form: { addEventListener() {} }, addEventListener: (event, fn) => { handlers[event] = fn; } };
    const status = {};
    const submit = { firstChild: {} };
    const elements = {
        whatsapp: phone,
        'reward-status': status,
        'reward-reminder': { querySelector: (selector) => fields[selector] },
        'btn-submit-lead': submit,
    };
    let timer;
    let reward = { titulo: 'Aula gratuita com certificado', icone: '🎓', ja_encontrou: false, maximo_anterior: false };
    vm.runInNewContext(script, {
        document: { getElementById: (id) => elements[id], querySelector: () => ({ content: 'csrf-test' }) },
        FormData, AbortController,
        setTimeout: (fn) => { timer = fn; }, clearTimeout() {},
        fetch: async (url, options) => {
            assert.equal(url, '/participar/TEST');
            assert.equal(options.body.get('consultar_premio'), '1');
            assert.equal(options.body.get('whatsapp'), phone.value);
            return { ok: true, headers: { get: () => 'application/json' }, json: async () => reward };
        },
    });
    phone.value = '(35) 98888-1111';
    handlers.input();
    await timer();
    assert.equal(fields.strong.textContent, 'Aula gratuita com certificado');
    assert.match(submit.firstChild.textContent, /RECEBER MEU PRÊMIO/);
    reward = { ...reward, ja_encontrou: true };
    handlers.change();
    await timer();
    assert.match(status.textContent, /já foi contabilizado/);
    assert.match(submit.firstChild.textContent, /VER MEU PROGRESSO/);
    phone.value = '123';
    handlers.input();
    await timer();
    assert.equal(fields.strong.textContent, 'Informe seu celular');
});
