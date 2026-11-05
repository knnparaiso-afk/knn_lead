(() => {
  'use strict';

  const dialog = document.getElementById('share-dialog');
  const opener = document.querySelector('.share-open');
  if (!dialog || !opener || typeof dialog.showModal !== 'function') return;

  const url = dialog.dataset.shareUrl;
  const title = 'KNN Paraisópolis';
  const text = 'Conheça a KNN Paraisópolis: aula grátis, comunidade e site oficial.';
  const encodedUrl = encodeURIComponent(url);
  const encodedMessage = encodeURIComponent(`${text} ${url}`);
  const field = dialog.querySelector('#share-link');
  const status = dialog.querySelector('.share-status');
  const copyButtons = [...dialog.querySelectorAll('[data-copy-link]')];
  const copyLabels = copyButtons.map(button => button.querySelector('[data-copy-label]'));
  const originalLabels = copyLabels.map(label => label.textContent);
  const networks = dialog.querySelector('.share-networks');
  const scrollNext = dialog.querySelector('.share-scroll');
  function updateScroll() {
    scrollNext.hidden = networks.scrollLeft + networks.clientWidth >= networks.scrollWidth - 2;
  }
  networks.addEventListener('scroll', updateScroll);
  window.addEventListener('resize', updateScroll);
  scrollNext.addEventListener('click', () => {
    networks.scrollBy({ left: 240, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  });
  const destinations = {
    x: `https://x.com/intent/tweet?text=${encodedMessage}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
    whatsapp: `https://wa.me/?text=${encodedMessage}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`,
    messenger: 'https://www.messenger.com/new',
    snapchat: `snapchat://creativeKitWeb/camera/1?attachmentUrl=${encodedUrl}`,
    email: `mailto:?subject=${encodeURIComponent(title)}&body=${encodedMessage}`,
  };

  dialog.querySelectorAll('[data-share-network]').forEach(link => {
    link.href = destinations[link.dataset.shareNetwork];
  });

  opener.hidden = false;
  opener.addEventListener('click', () => {
    status.textContent = '';
    copyLabels.forEach((label, index) => { label.textContent = originalLabels[index]; });
    dialog.showModal();
    networks.scrollLeft = 0;
    updateScroll();
    document.documentElement.classList.add('share-is-open');
  });
  dialog.querySelector('.share-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const focusable = [...dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), [tabindex="0"]')]
      .filter(element => !element.hidden && element.getClientRects().length > 0);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right
        || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('share-is-open');
    opener.focus({ preventScroll: true });
  });

  async function copyLink() {
    const previousFocus = document.activeElement;
    let copied = false;
    try {
      await navigator.clipboard.writeText(url);
      copied = true;
    } catch {
      field.focus();
      field.select();
      field.setSelectionRange(0, field.value.length);
      try { copied = document.execCommand('copy'); } catch { /* Seleção manual abaixo. */ }
    }
    if (copied) {
      status.textContent = 'Link copiado!';
      copyLabels.forEach(label => { label.textContent = 'Copiado!'; });
      previousFocus?.focus({ preventScroll: true });
    } else {
      status.textContent = 'Selecione e copie o link acima para compartilhar.';
    }
  }
  copyButtons.forEach(button => button.addEventListener('click', copyLink));

  const nativeShare = dialog.querySelector('[data-native-share]');
  if (typeof navigator.share === 'function') {
    nativeShare.hidden = false;
    nativeShare.addEventListener('click', async () => {
      try {
        await navigator.share({ title, text, url });
      } catch (error) {
        if (error.name !== 'AbortError') status.textContent = 'Escolha uma rede acima ou copie o link.';
      }
    });
  }
})();
