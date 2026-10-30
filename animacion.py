"""
animacion.py - Reproductor propio para las figuras animadas de Plotly.

Los botones de animación que trae Plotly quedaban fuera del área visible y no
funcionaban bien en pantalla completa. Aquí la figura se incrusta en una página
HTML con su propia barra de control (reproducir, pausa, reiniciar, velocidad,
línea de tiempo y pantalla completa) que ocupa todo el espacio disponible.
"""

CSS = """
html,body{margin:0;height:100%;background:#0B1722;overflow:hidden}
#wrap{display:flex;flex-direction:column;height:100vh;background:#0B1722;
      font-family:'Space Grotesk',system-ui,sans-serif;color:#E6EEF5}
#plotbox{flex:1 1 auto;min-height:0;order:1;position:relative}
#plotbox>div{height:100%}
#barra{order:2;display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:10px 16px;
       background:linear-gradient(180deg,#10263a,#0B1722);border-top:1px solid #23415b}
.btn{border:0;border-radius:999px;padding:11px 24px;font:700 15px 'Space Grotesk',system-ui,sans-serif;
     cursor:pointer;transition:transform .12s,box-shadow .2s,filter .2s;white-space:nowrap}
.btn:active{transform:scale(.97)}
#play{background:linear-gradient(135deg,#19E3B1,#2BB7FF);color:#04202E;
      box-shadow:0 4px 14px rgba(43,183,255,.35)}
#play:hover{transform:translateY(-1px);box-shadow:0 8px 22px rgba(43,183,255,.55)}
#play.pausa{background:linear-gradient(135deg,#FFC24D,#FF7A59);color:#2b1300;
            box-shadow:0 4px 14px rgba(255,122,89,.4)}
.sec{background:#14304a;color:#E6EEF5;border:1.5px solid #3b6384;padding:10px 18px}
.sec:hover{background:#1c4263;border-color:#5aa9e6}
#rng{flex:1 1 180px;min-width:140px;accent-color:#2BB7FF;height:6px;cursor:pointer}
select{background:#14304a;color:#E6EEF5;border:1.5px solid #3b6384;border-radius:999px;
       padding:9px 12px;font:600 14px 'Space Grotesk',system-ui,sans-serif;cursor:pointer}
#msg{color:#FFB347;font-size:13px}
"""

BARRA = """
<div id="barra">
  <button class="btn" id="play">▶&nbsp; Reproducir</button>
  <button class="btn sec" id="rst" title="Volver al inicio">⟲ Reiniciar</button>
  <input type="range" id="rng" min="0" max="1" value="0" step="1" title="Línea de tiempo">
  <select id="spd" title="Velocidad de la animación">
    <option value="0.5">×0.5</option><option value="1" selected>×1</option>
    <option value="2">×2</option><option value="4">×4</option>
  </select>
  __ROT__
  <button class="btn sec" id="fs">⛶&nbsp; Pantalla completa</button>
  <span id="msg"></span>
</div>
"""

JS = """
(function () {
  var gd = document.getElementById("__ID__");
  var names = __NOMBRES__;
  var base = __BASE__;
  var btn = document.getElementById("play"), rng = document.getElementById("rng"),
      rst = document.getElementById("rst"), spd = document.getElementById("spd"),
      fs = document.getElementById("fs"), msg = document.getElementById("msg"),
      wrap = document.getElementById("wrap");
  var rot = document.getElementById("rot");
  var playing = false, cur = 0;
  rng.max = Math.max(1, names.length - 1);
  rng.value = 0;

  function dur() { return Math.max(8, base / parseFloat(spd.value)); }
  function setPlay(p) {
    playing = p;
    btn.innerHTML = p ? "❚❚&nbsp; Pausa" : "▶&nbsp; Reproducir";
    btn.classList.toggle("pausa", p);
  }
  function parar() {
    Plotly.animate(gd, [null], {frame: {duration: 0, redraw: false},
                                transition: {duration: 0}, mode: "immediate"});
  }
  function reproducir(lista) {
    Plotly.animate(gd, lista, {frame: {duration: dur(), redraw: true},
                               transition: {duration: 0}, mode: "immediate",
                               fromcurrent: true});
  }
  function irA(i) {
    cur = i; rng.value = i;
    Plotly.animate(gd, [names[i]], {frame: {duration: 0, redraw: true},
                                    transition: {duration: 0}, mode: "immediate"});
  }

  btn.onclick = function () {
    if (playing) { parar(); setPlay(false); }
    else {
      var k = (cur >= names.length - 1) ? 0 : cur;
      setPlay(true);
      reproducir(names.slice(k));
    }
  };
  rst.onclick = function () { if (playing) { parar(); } setPlay(false); irA(0); };
  rng.oninput = function () {
    if (playing) { parar(); setPlay(false); }
    irA(parseInt(rng.value, 10));
  };
  spd.onchange = function () { if (playing) { reproducir(names.slice(cur)); } };

  gd.on("plotly_animatingframe", function (ev) {
    var i = names.indexOf(ev.name);
    if (i >= 0) { cur = i; rng.value = i; }
  });
  gd.on("plotly_animated", function () {
    if (cur >= names.length - 1) { setPlay(false); }
  });

  var girando = false, ang = 0, ojo = null;
  function giro() {
    if (!girando) { return; }
    ang += 0.04;
    var r = Math.hypot(ojo.x, ojo.y), a0 = Math.atan2(ojo.y, ojo.x);
    Plotly.relayout(gd, {"scene.camera.eye": {x: r * Math.cos(a0 + ang), y: r * Math.sin(a0 + ang), z: ojo.z}});
    setTimeout(giro, 70);
  }
  if (rot) {
    rot.onclick = function () {
      if (!ojo) {
        var cam = gd.layout && gd.layout.scene && gd.layout.scene.camera;
        ojo = (cam && cam.eye) ? {x: cam.eye.x, y: cam.eye.y, z: cam.eye.z} : {x: 1.5, y: -1.5, z: 1.0};
      }
      girando = !girando;
      rot.innerHTML = girando ? "■&nbsp; Detener giro" : "⟳&nbsp; Girar vista";
      if (girando) { giro(); }
    };
  }

  function enPantallaCompleta() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement);
  }
  fs.onclick = function () {
    msg.textContent = "";
    if (enPantallaCompleta()) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      return;
    }
    var f = wrap.requestFullscreen || wrap.webkitRequestFullscreen;
    var aviso = "El navegador no permitió la pantalla completa. Usa F11 o sube la altura del gráfico.";
    if (!f) { msg.textContent = aviso; return; }
    try {
      var r = f.call(wrap);
      if (r && r.catch) { r.catch(function () { msg.textContent = aviso; }); }
    } catch (e) { msg.textContent = aviso; }
  };
  function alCambiar() {
    fs.innerHTML = enPantallaCompleta() ? "✕&nbsp; Salir" : "⛶&nbsp; Pantalla completa";
    setTimeout(function () { Plotly.Plots.resize(gd); }, 120);
  }
  document.addEventListener("fullscreenchange", alCambiar);
  document.addEventListener("webkitfullscreenchange", alCambiar);
  window.addEventListener("resize", function () { Plotly.Plots.resize(gd); });
})();
"""


def construir_js(nombres, paso_ms, div_id):
    import json
    return (JS.replace("__ID__", div_id)
              .replace("__NOMBRES__", json.dumps(list(nombres)))
              .replace("__BASE__", str(int(paso_ms))))


def construir_html(fig, nombres, paso_ms=40, div_id="grafico", rotar=False):
    """Devuelve una página HTML completa con la figura y su barra de control."""
    plot = fig.to_html(
        full_html=False, include_plotlyjs="cdn", div_id=div_id, auto_play=False,
        default_width="100%", default_height="100%",
        config={"responsive": True, "displaylogo": False},
        post_script=construir_js(nombres, paso_ms, div_id),
    )
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<link href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap' rel='stylesheet'>"
            "<style>" + CSS + "</style></head><body><div id='wrap'>" +
            BARRA.replace("__ROT__", "<button class=\"btn sec\" id=\"rot\">⟳&nbsp; Girar vista</button>" if rotar else "") +
            "<div id='plotbox'>" + str(plot) + "</div></div></body></html>")
