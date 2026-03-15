(async function () {
  try {
    const res = await fetch('/api/settings/public');
    if (!res.ok) return;
    const { google_analytics_id: gaId } = await res.json();
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
