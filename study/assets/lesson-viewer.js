(() => {
  const buttons = [...document.querySelectorAll('[data-tab]')];
  const panels = {ff: document.getElementById('ff-panel'), cc: document.getElementById('cc-panel')};
  const frame = document.getElementById('cc-frame');
  const enterFrame = () => {
    frame.scrollIntoView({block: 'start'});
    frame.focus({preventScroll: true});
    try { frame.contentWindow?.focus(); } catch (_) { /* Focusing the iframe element is sufficient. */ }
  };
  const activate = (name, enter = false) => {
    if (!panels[name]) name = 'ff';
    buttons.forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === name)));
    Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== name; });
    if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
    if (name === 'cc') {
      resizeFrame();
      if (enter) requestAnimationFrame(enterFrame);
    }
  };
  const renderRaw = text => `<pre class="raw-fallback"></pre>`;
  fetch('./ff.md', {cache: 'no-store'})
    .then(response => { if (!response.ok) throw new Error(`FF ${response.status}`); return response.text(); })
    .then(text => {
      if (window.marked && window.DOMPurify) panels.ff.innerHTML = DOMPurify.sanitize(marked.parse(text));
      else { panels.ff.innerHTML = renderRaw(text); panels.ff.querySelector('pre').textContent = text; }
    })
    .catch(error => { panels.ff.innerHTML = `<p>FF 내용을 불러오지 못했습니다.</p><pre></pre>`; panels.ff.querySelector('pre').textContent = String(error); });
  function resizeFrame() {
    try {
      const doc = frame.contentDocument;
      if (doc) frame.style.height = `${Math.max(640, doc.documentElement.scrollHeight, doc.body?.scrollHeight || 0)}px`;
    } catch (_) { /* The direct link remains available if iframe inspection fails. */ }
  }
  frame.addEventListener('load', () => {
    resizeFrame();
    setTimeout(resizeFrame, 500);
    setTimeout(resizeFrame, 1500);
    if (location.hash === '#cc') enterFrame();
  });
  buttons.forEach(button => button.addEventListener('click', () => {
    const name = button.dataset.tab;
    activate(name, name === 'cc');
  }));
  addEventListener('hashchange', () => {
    const name = location.hash.slice(1);
    activate(name, name === 'cc');
  });
  addEventListener('resize', resizeFrame);
  const initialTab = location.hash.slice(1) || 'ff';
  activate(initialTab, initialTab === 'cc');
})();
