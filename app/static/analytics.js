(async function () {
  try {
    const res = await fetch('/api/settings/public');
    if (!res.ok) return;
    const { shop_name: shopName, google_analytics_id: gaId } = await res.json();

    // ── Dynamic title ───────────────────────────────────────────────────────
    if (shopName) {
      const suffix = document.title;
      document.title = suffix ? shopName + ' — ' + suffix : shopName;
    }

    // ── Open Graph tags (TV and status pages only) ──────────────────────────
    const path = window.location.pathname.replace(/\/$/, '');
    if (path === '/tv' || path === '' || path === '/status') {
      function setOG(property, content) {
        let el = document.querySelector('meta[property="' + property + '"]');
        if (!el) {
          el = document.createElement('meta');
          el.setAttribute('property', property);
          document.head.appendChild(el);
        }
        el.setAttribute('content', content);
      }
      const title = document.title;
      const descEl = document.querySelector('meta[name="description"]');
      const desc = descEl ? descEl.getAttribute('content') : '';
      setOG('og:title', title);
      if (desc) setOG('og:description', desc);
      setOG('og:url', window.location.href);
    }

    // ── Google Analytics ────────────────────────────────────────────────────
    if (!gaId) return;
    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(gaId);
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag() { dataLayer.push(arguments); }
    gtag('js', new Date());
    gtag('config', gaId);
  } catch (_) {}
})();
