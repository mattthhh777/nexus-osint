// Graphite & Ember theme flag - opt-in only, default OFF.
// Activates via ?theme=graphite query param OR cookie `ui_theme=graphite`.
// When active, adds class `nx-v2` to <html> and loads tokens-graphite.css.

(function () {
  'use strict';

  function getParam(name) {
    var match = new RegExp('[?&]' + name + '=([^&]+)').exec(window.location.search);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
  }

  var fromParam = getParam('theme');
  var fromCookie = getCookie('ui_theme');
  var active = fromParam === 'graphite' || fromCookie === 'graphite';

  if (active) {
    document.documentElement.classList.add('nx-v2');
    if (fromParam === 'graphite' && fromCookie !== 'graphite') {
      var expires = new Date();
      expires.setDate(expires.getDate() + 30);
      document.cookie = 'ui_theme=graphite; expires=' + expires.toUTCString() + '; path=/; SameSite=Lax';
    }

    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/tokens-graphite.css?v=20260518';
    document.head.appendChild(link);

    var connectorsCss = document.createElement('link');
    connectorsCss.rel = 'stylesheet';
    connectorsCss.href = '/static/css/connectors.css?v=20260518';
    document.head.appendChild(connectorsCss);
  }

  window.NX_V2 = active;
})();
