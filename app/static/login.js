// Lock-screen behaviour. Loaded as an external script because the page CSP
// (script-src 'self') blocks inline scripts. The failed-password error is
// rendered server-side (see login_get in main.py), so JS is only progressive
// enhancement here — the page is fully functional without it.
(function () {
  "use strict";

  var form = document.querySelector("form");
  if (!form) return;

  // Submit affordance: swap the button label for the canonical spinner and
  // block double-submits. The form POST has already begun, so disabling the
  // button does not cancel it.
  form.addEventListener("submit", function () {
    var btn = form.querySelector(".login-submit");
    if (!btn) return;
    btn.setAttribute("aria-busy", "true");
    btn.disabled = true;
  });
})();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  });
}
