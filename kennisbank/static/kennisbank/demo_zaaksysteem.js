(function () {
  var sel = document.getElementById("zsType");
  sel.addEventListener("change", function () {
    document.getElementById("kb").src = "/zaaktype/" + encodeURIComponent(sel.value);
  });
})();
