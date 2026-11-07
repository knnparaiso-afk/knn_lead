(() => {
  const dialog = document.querySelector('[data-roleta]');
  const opener = document.querySelector('[data-roleta-open]');
  if (!dialog || !opener || typeof dialog.showModal !== 'function') return;

  const seenKey = 'knn-roleta-vista';
  const wasSeen = () => {
    try { return sessionStorage.getItem(seenKey) === '1'; }
    catch { return false; }
  };
  const open = () => {
    dialog.showModal();
    try { sessionStorage.setItem(seenKey, '1'); } catch {}
  };

  opener.hidden = false;
  opener.addEventListener('click', open);
  dialog.querySelectorAll('[data-roleta-close]').forEach(button => {
    button.addEventListener('click', () => dialog.close());
  });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => opener.focus({ preventScroll: true }));
  if (!wasSeen()) open();

  const form = dialog.querySelector('[data-roleta-form]');
  if (!form) return;

  const button = form.querySelector('[data-roleta-spin]');
  const status = dialog.querySelector('[data-roleta-status]');
  const disc = dialog.querySelector('[data-roleta-disc]');
  const title = dialog.querySelector('[data-roleta-title]');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = 'Girando…';
    status.textContent = '';

    let resultado;
    let mensagemErro = 'O giro não carregou. Tente novamente ou atualize a página.';
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      resultado = await response.json();
      if (!response.ok) {
        mensagemErro = resultado.erro || mensagemErro;
        throw new Error(mensagemErro);
      }
    } catch {
      status.textContent = mensagemErro;
      button.textContent = 'Tentar novamente';
      button.disabled = false;
      return;
    } finally {
      window.clearTimeout(timeout);
    }

    if (dialog.open && !reducedMotion.matches && disc.animate) {
      const rotation = `rotate(${2160 - 60 * resultado.fatia}deg)`;
      const spin = disc.animate([
        { transform: 'rotate(0deg)', easing: 'ease-in' },
        { transform: 'rotate(205deg)', offset: .12, easing: 'cubic-bezier(.13, .54, .22, 1)' },
        { transform: rotation, offset: .86 },
        { transform: rotation },
      ], { duration: 3250, fill: 'forwards' });
      await spin.finished.catch(() => {});
    }

    title.textContent = 'Você ganhou!';
    dialog.querySelector('[data-roleta-intro]').hidden = true;
    dialog.querySelector('[data-roleta-wheel]').hidden = true;
    dialog.querySelector('[data-roleta-prize]').textContent = resultado.premio;
    dialog.querySelectorAll('[data-roleta-icon]').forEach(icon => {
      icon.toggleAttribute('hidden', icon.dataset.roletaIcon !== resultado.tipo);
    });
    dialog.querySelector('[data-roleta-whatsapp]').href = resultado.whatsapp_url;
    dialog.querySelector('[data-roleta-reveal]').hidden = false;
    dialog.querySelector('[data-roleta-claim]').hidden = false;
    dialog.querySelector('[data-roleta-dismiss]').textContent = 'Continuar no site';
    form.hidden = true;
    if (dialog.open) title.focus({ preventScroll: true });
  });
})();
