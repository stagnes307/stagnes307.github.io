(() => {
  const frame = document.getElementById('cc-document');
  const mobile = matchMedia('(max-width: 680px)');
  if (!frame) return;

  let frameWindow = null;
  let lastScrollTop = 0;

  const setToolbarHidden = hidden => {
    document.body.classList.toggle('toolbar-hidden', mobile.matches && hidden);
  };

  const syncWithScroll = () => {
    if (!mobile.matches) {
      setToolbarHidden(false);
      return;
    }
    try {
      const scrollingElement = frame.contentDocument?.scrollingElement;
      const scrollTop = scrollingElement?.scrollTop ?? frameWindow?.scrollY ?? 0;
      if (scrollTop <= 0 || scrollTop < lastScrollTop) {
        setToolbarHidden(false);
      } else if (scrollTop > lastScrollTop && scrollTop > 12) {
        setToolbarHidden(true);
      }
      lastScrollTop = scrollTop;
    } catch (_) {
      setToolbarHidden(false);
    }
  };

  const bindFrameScroll = () => {
    try {
      frameWindow?.removeEventListener('scroll', syncWithScroll);
      frameWindow = frame.contentWindow;
      const scrollingElement = frame.contentDocument?.scrollingElement;
      lastScrollTop = scrollingElement?.scrollTop ?? frameWindow?.scrollY ?? 0;
      setToolbarHidden(false);
      frameWindow?.addEventListener('scroll', syncWithScroll, {passive: true});
    } catch (_) {
      frameWindow = null;
      setToolbarHidden(false);
    }
  };

  frame.addEventListener('load', bindFrameScroll);
  if (frame.contentDocument?.readyState === 'complete') bindFrameScroll();
  const handleViewportChange = () => {
    setToolbarHidden(false);
    bindFrameScroll();
  };
  if (mobile.addEventListener) mobile.addEventListener('change', handleViewportChange);
  else mobile.addListener(handleViewportChange);
})();
