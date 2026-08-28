(() => {
  const frame = document.getElementById('cc-document');
  const toggle = document.querySelector('[data-toolbar-toggle]');
  const mobile = matchMedia('(max-width: 680px)');
  if (!frame || !toggle) return;

  let frameWindow = null;

  const setCompact = compact => {
    const enabled = mobile.matches && compact;
    document.body.classList.toggle('toolbar-compact', enabled);
    toggle.setAttribute('aria-expanded', String(!enabled));
    const label = enabled ? '위쪽 도구 펼치기' : '위쪽 도구 접기';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
  };

  const syncWithScroll = () => {
    if (!mobile.matches) {
      setCompact(false);
      return;
    }
    try {
      const scrollingElement = frame.contentDocument?.scrollingElement;
      const scrollTop = scrollingElement?.scrollTop ?? frameWindow?.scrollY ?? 0;
      setCompact(scrollTop >= 24);
    } catch (_) {
      // Manual collapse remains available if the embedded document cannot be inspected.
    }
  };

  const bindFrameScroll = () => {
    try {
      frameWindow?.removeEventListener('scroll', syncWithScroll);
      frameWindow = frame.contentWindow;
      frameWindow?.addEventListener('scroll', syncWithScroll, {passive: true});
      syncWithScroll();
    } catch (_) {
      frameWindow = null;
    }
  };

  frame.addEventListener('load', bindFrameScroll);
  if (frame.contentDocument?.readyState === 'complete') bindFrameScroll();
  toggle.addEventListener('click', () => {
    setCompact(!document.body.classList.contains('toolbar-compact'));
  });
  const handleViewportChange = () => syncWithScroll();
  if (mobile.addEventListener) mobile.addEventListener('change', handleViewportChange);
  else mobile.addListener(handleViewportChange);
})();
