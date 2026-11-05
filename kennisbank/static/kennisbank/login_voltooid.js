/* Hulpvenster voor inloggen vanuit een iframe (zaaksysteem). */
(function () {
  var el = document.getElementById("login-voltooid");
  if (el.dataset.auth !== "1") {
    // Nog niet ingelogd: door naar de loginpagina, en daarna terug naar deze pagina.
    location.reload();
    return;
  }
  if (window.opener) {
    window.opener.postMessage("kb-ingelogd", location.origin);
    window.close();
  }
})();
