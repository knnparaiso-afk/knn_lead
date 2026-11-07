(() => {
  const dialog = document.querySelector('[data-roleta]');
  const opener = document.querySelector('[data-roleta-open]');
  if (!dialog || !opener || typeof dialog.showModal !== 'function') return;

  const seenKey = 'knn-roleta-vista';
  const wasSeen = () => {
    try { return sessionStorage.getItem(seenKey) === '1'; }
    catch { return false; }
  };
  const viewport = window.visualViewport;
  const fitDialog = () => {
    if (!dialog.open) return;
    const visibleViewport = viewport?.scale === 1 ? viewport : null;
    const height = visibleViewport?.height ?? window.innerHeight;
    const top = visibleViewport?.offsetTop ?? 0;
    const bottom = Math.max(0, window.innerHeight - height - top);
    dialog.style.setProperty('--roleta-viewport-height', `${height}px`);
    dialog.style.setProperty('--roleta-viewport-top', `${top}px`);
    dialog.style.setProperty('--roleta-viewport-bottom', `${bottom}px`);
    dialog.classList.toggle('is-short', height < 540);
  };
  const open = () => {
    dialog.showModal();
    fitDialog();
    try { sessionStorage.setItem(seenKey, '1'); } catch {}
  };

  window.addEventListener('resize', fitDialog);
  viewport?.addEventListener('resize', fitDialog);
  viewport?.addEventListener('scroll', fitDialog);
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

  const startClaim = dialog.querySelector('[data-roleta-start-claim]');
  const claimForm = dialog.querySelector('[data-roleta-claim-form]');
  const claimButton = claimForm.querySelector('button');
  const claimButtonText = claimButton.querySelector('span');
  const claimStatus = dialog.querySelector('[data-roleta-claim-status]');
  const phone = claimForm.elements.whatsapp;
  const whatsapp = dialog.querySelector('[data-roleta-whatsapp]');

  startClaim.addEventListener('click', () => {
    startClaim.hidden = true;
    claimForm.hidden = false;
    dialog.classList.add('is-claiming');
    phone.focus({ preventScroll: true });
  });
  const maskPhone = event => {
    const raw = phone.value;
    let digits = raw.replace(/\D/g, '');
    let digitsBeforeCaret = raw.slice(0, phone.selectionStart).replace(/\D/g, '').length;
    // Aceita colar com o código do Brasil, sem confundir com o DDD 55.
    if (!raw.startsWith('(') && digits.startsWith('55') && (digits.length === 12 || digits.length === 13)) {
      digits = digits.slice(2);
      digitsBeforeCaret -= 2;
    }
    let formatted = digits ? `(${digits.slice(0, 2)}` : '';
    if (digits.length > 2) {
      const split = digits[2] === '9' ? 7 : 6;
      formatted += `) ${digits.slice(2, split)}`;
      if (digits.length > split) formatted += `-${digits.slice(split)}`;
    }
    if (raw !== formatted) {
      // Mantém o cursor junto ao dígito editado, inclusive no meio do número.
      let caret = 0;
      while (caret < formatted.length && digitsBeforeCaret > 0) {
        if (/\d/.test(formatted[caret])) digitsBeforeCaret--;
        caret++;
      }
      if (event?.inputType === 'deleteContentForward') {
        while (caret < formatted.length && /\D/.test(formatted[caret])) caret++;
      }
      phone.value = formatted;
      phone.setSelectionRange(caret, caret);
    }
    return digits;
  };
  phone.addEventListener('input', event => {
    maskPhone(event);
    phone.removeAttribute('aria-invalid');
    claimStatus.textContent = '';
  });
  claimForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (claimButton.disabled) return;
    if (!/^[1-9][0-9](?:9[0-9]{8}|[2-5][0-9]{7})$/.test(maskPhone())) {
      phone.setAttribute('aria-invalid', 'true');
      claimStatus.textContent = 'Digite um número de WhatsApp válido com DDD.';
      phone.focus({ preventScroll: true });
      return;
    }
    const data = new FormData(claimForm);
    claimButton.disabled = phone.readOnly = true;
    claimButtonText.textContent = 'Vinculando seu prêmio…';
    claimStatus.textContent = '';
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    let errorMessage = 'Não deu para vincular o prêmio agora. Tente de novo.';
    try {
      const response = await fetch(claimForm.action, {
        method: 'POST', body: data, headers: { Accept: 'application/json' }, signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok) {
        errorMessage = result.erro || errorMessage;
        if (response.status === 400 || response.status === 409) phone.setAttribute('aria-invalid', 'true');
        throw new Error(errorMessage);
      }
      whatsapp.href = result.whatsapp_url;
      claimForm.hidden = true;
      dialog.classList.remove('is-claiming');
      dialog.querySelector('[data-roleta-ready]').hidden = false;
      if (dialog.open) {
        whatsapp.focus({ preventScroll: true });
        window.location.assign(whatsapp.href);
      }
    } catch {
      claimStatus.textContent = errorMessage;
      if (dialog.open && phone.hasAttribute('aria-invalid')) phone.focus({ preventScroll: true });
    } finally {
      window.clearTimeout(timeout);
      claimButton.disabled = phone.readOnly = false;
      claimButtonText.textContent = 'Continuar para o WhatsApp';
    }
  });

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

    if (dialog.open && reducedMotion.matches && disc.animate) {
      // Um ajuste curto após o toque, sem as voltas e a aceleração do giro completo.
      const angle = (360 - 60 * resultado.fatia) % 360;
      const spin = disc.animate([
        { transform: `rotate(${angle - 60}deg)` },
        { transform: `rotate(${angle}deg)` },
      ], { duration: 550, easing: 'ease-out', fill: 'forwards' });
      await spin.finished.catch(() => {});
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
    dialog.querySelector('[data-roleta-reveal]').hidden = false;
    dialog.querySelector('[data-roleta-claim]').hidden = false;
    dialog.querySelector('[data-roleta-dismiss]').textContent = 'Continuar no site';
    form.hidden = true;
    if (dialog.open) title.focus({ preventScroll: true });
  });
})();
