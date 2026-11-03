// Abre la noticia que viene en el link de Telegram (#n3) y maneja el botón "Abrir todas".
(function () {
  function abrirDesdeLink() {
    var id = decodeURIComponent(location.hash.slice(1));
    var nota = id && document.getElementById(id);
    if (!nota) return;
    var det = nota.querySelector("details");
    if (det) det.open = true;
    nota.scrollIntoView({ block: "start" });
  }
  window.addEventListener("hashchange", abrirDesdeLink);
  abrirDesdeLink();

  var boton = document.getElementById("todo");
  if (!boton) return;
  boton.addEventListener("click", function () {
    var todos = document.querySelectorAll(".nota details");
    var abrir = Array.prototype.some.call(todos, function (d) { return !d.open; });
    todos.forEach(function (d) { d.open = abrir; });
    boton.textContent = abrir ? "Cerrar todas" : "Abrir todas";
  });
})();
