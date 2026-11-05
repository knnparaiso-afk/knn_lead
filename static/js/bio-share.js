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
  const scrollPrev = dialog.querySelector('.share-scroll-prev');
  const scrollNext = dialog.querySelector('.share-scroll-next');
  let scrollTarget = null;
  function updateScroll() {
    const maxScroll = Math.max(0, networks.scrollWidth - networks.clientWidth);
    const overflowing = maxScroll > 2;
    scrollPrev.hidden = scrollNext.hidden = !overflowing;
    scrollPrev.disabled = networks.scrollLeft <= 2;
    scrollNext.disabled = networks.scrollLeft >= maxScroll - 2;
    if (scrollTarget !== null && Math.abs(networks.scrollLeft - scrollTarget) <= 2) scrollTarget = null;
  }
  function navigateOptions(direction) {
    const firstOption = networks.querySelector('.share-option');
    const gap = parseFloat(window.getComputedStyle(networks).columnGap) || 0;
    const step = firstOption.offsetWidth + gap;
    const page = Math.max(1, Math.floor((networks.clientWidth + gap) / step)) * step;
    const maxScroll = Math.max(0, networks.scrollWidth - networks.clientWidth);
    scrollTarget = Math.max(0, Math.min(maxScroll, (scrollTarget ?? networks.scrollLeft) + direction * page));
    networks.scrollTo({ left: scrollTarget, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    updateScroll();
  }
  function cancelScrollTarget() { scrollTarget = null; }
  networks.addEventListener('scroll', updateScroll);
  networks.addEventListener('scrollend', cancelScrollTarget);
  ['pointerdown', 'wheel', 'keydown'].forEach(event => networks.addEventListener(event, cancelScrollTarget));
  window.addEventListener('resize', updateScroll);
  if (typeof ResizeObserver === 'function') new ResizeObserver(updateScroll).observe(networks);
  scrollPrev.addEventListener('click', () => navigateOptions(-1));
  scrollNext.addEventListener('click', () => navigateOptions(1));
  const destinations = {
    x: `https://x.com/intent/tweet?text=${encodedMessage}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
    whatsapp: `https://wa.me/?text=${encodedMessage}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`,
    messenger: 'https://www.messenger.com/new',
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
    scrollTarget = null;
    networks.scrollTo({ left: 0, behavior: 'instant' });
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
