"""Convierte las ediciones en la página web y arma el mensaje de Telegram.

Uso:
  python scripts/publicar.py --sitio                      arma _sitio/ con todas las ediciones
  python scripts/publicar.py --fecha F --solo-mensaje     muestra el mensaje de Telegram de esa fecha
La URL pública del sitio se toma de --base-url o de la variable SITIO_URL.
"""
import argparse
import html
import os
import shutil

from comun import (EDICIONES, RAIZ, SITIO, consola_utf8, ediciones_anteriores, fecha_larga,
                   leer_json)

VERACIDAD = {
    "oficial": ("🟢", "Oficial", "La anunció la propia empresa u organismo."),
    "confirmada": ("🔵", "Confirmada", "La publican al menos dos medios serios."),
    "sin_confirmar": ("🟠", "Sin confirmar", "Una sola fuente o rumor: tomar con pinzas."),
}
BASE_JON = {
    "resumen_escrito": "Basado en el resumen escrito que Jon publica de cada video de noticias.",
    "descripcion": "Basado en la descripción y los temas del video: no incluye todo lo que se dice en él.",
}
TIPO_FUENTE = {"oficial": "Oficial", "medio": "Medio", "especialista": "Especialista", "jon": "Jon Hernández"}


def e(texto):
    return html.escape(str(texto or ""), quote=True)


def url_jon(ed, segundo):
    return f"https://www.youtube.com/watch?v={ed['jon_video']['id']}&t={int(segundo)}s"


def ultimo_video_jon(fecha):
    """Última edición anterior a `fecha` que trajo un video de Jon, o None."""
    for ed in reversed(ediciones_anteriores(fecha, 30)):
        if ed.get("jon_video"):
            return ed
    return None


def aviso_sin_video(previa):
    """Texto para los días en que Jon no subió un video nuevo."""
    fecha = fecha_larga(previa["fecha"]).split(" ", 1)[1].rsplit(" de ", 1)[0]
    return f"Jon Hernández no subió un video nuevo. El último salió en el resumen del {fecha}:"


def marca(segundo):
    return f"{int(segundo) // 60}:{int(segundo) % 60:02d}"


# ------------------------------------------------------------------ Telegram

def mensaje_telegram(ed, base_url):
    """Devuelve (texto en HTML de Telegram, teclado de botones)."""
    pagina = f"{base_url.rstrip('/')}/{ed['fecha']}.html"
    fecha = fecha_larga(ed["fecha"]).rsplit(" de ", 1)[0]  # sin el año
    lineas = [f"🤖 <b>Noticias de IA</b> · {e(fecha)}", "", f"<i>{e(ed['intro'])}</i>", ""]
    for i, n in enumerate(ed["noticias"], 1):
        emoji = VERACIDAD[n["veracidad"]][0]
        lineas.append(f"{emoji} <b>{i}. {e(n['titulo'])}</b>")
        lineas.append(e(n["breve"]))
        lineas.append("")
    if ed.get("jon_video"):
        v = ed["jon_video"]
        lineas.append(f"📺 Jon Hernández: <a href=\"https://www.youtube.com/watch?v={e(v['id'])}\">{e(v['titulo'])}</a>")
        if ed.get("jon_resumen"):
            lineas.append("El resumen completo del video llega en el mensaje siguiente.")
        lineas.append("")
    previa = None if ed.get("jon_video") else ultimo_video_jon(ed["fecha"])
    if previa:
        lineas.append(f"📺 {e(aviso_sin_video(previa))} "
                      f"<a href=\"{base_url.rstrip('/')}/{previa['fecha']}.html#jon\">{e(previa['jon_video']['titulo'])}</a>")
        lineas.append("")
    lineas.append("🟢 oficial · 🔵 confirmada · 🟠 sin confirmar")
    texto = "\n".join(lineas)

    botones = [{"text": f"{i} · {n['titulo_corto']}", "url": f"{pagina}#n{i}"}
               for i, n in enumerate(ed["noticias"], 1)]
    filas = [botones[k:k + 2] for k in range(0, len(botones), 2)]
    if ed.get("jon_resumen"):
        filas.append([{"text": "📺 Resumen del video de Jon", "url": f"{pagina}#jon"}])
    elif previa:
        filas.append([{"text": "📺 Último video de Jon", "url": f"{base_url.rstrip('/')}/{previa['fecha']}.html#jon"}])
    filas.append([{"text": "📰 Ver la edición completa", "url": pagina}])
    return texto, {"inline_keyboard": filas}


def mensaje_jon(ed):
    """Segundo mensaje de Telegram con el resumen largo del video, o None si no hay."""
    r = ed.get("jon_resumen")
    if not r or not ed.get("jon_video"):
        return None
    v = ed["jon_video"]
    lineas = ["📺 <b>Video de Jon Hernández</b>",
              f"<a href=\"https://www.youtube.com/watch?v={e(v['id'])}\">{e(v['titulo'])}</a>", "",
              f"<i>{e(r['de_que_trata'])}</i>", ""]
    for parrafo in r["explicacion"]:
        lineas += [e(parrafo), ""]
    lineas.append("<b>Puntos clave</b>")
    for p in r["puntos_clave"]:
        if p.get("segundo") is not None:
            lineas.append(f"• {e(p['texto'])} <a href=\"{e(url_jon(ed, p['segundo']))}\">({marca(p['segundo'])})</a>")
        else:
            lineas.append(f"• {e(p['texto'])}")
    lineas += ["", f"<i>{e(BASE_JON[r['base']])}</i>"]
    return "\n".join(lineas)


# ------------------------------------------------------------------ Página web

def html_noticia(ed, i, n):
    emoji, etiqueta, explicacion = VERACIDAD[n["veracidad"]]
    partes = [f'<article class="nota" id="n{i}"><details>',
              '<summary>',
              f'<div class="meta"><span class="num">{i}</span><span class="chip">{e(n["categoria"])}</span>'
              f'<span class="chip ver-{e(n["veracidad"])}" title="{e(explicacion)}">{emoji} {e(etiqueta)}</span></div>',
              f'<h2>{e(n["titulo"])}</h2>',
              f'<p class="breve">{e(n["breve"])}</p>',
              '<span class="mas">Ver más</span>',
              '</summary><div class="cuerpo">']
    partes += [f"<p>{e(p)}</p>" for p in n["detalle"]]
    partes.append(f'<div class="caja importa"><strong>Por qué importa</strong><p>{e(n["por_que_importa"])}</p></div>')
    if n.get("jon_opina") or n.get("jon_segundo") is not None:
        partes.append('<div class="caja jon"><strong>Jon Hernández</strong>')
        if n.get("jon_opina"):
            partes.append(f"<p>{e(n['jon_opina'])}</p>")
        if n.get("jon_segundo") is not None and ed.get("jon_video"):
            seg = int(n["jon_segundo"])
            partes.append(f'<p><a href="{e(url_jon(ed, seg))}" target="_blank" rel="noopener">'
                          f'▶ Verlo en su video (minuto {marca(seg)})</a></p>')
        partes.append("</div>")
    partes.append('<div class="fuentes"><strong>Fuentes</strong><ul>')
    for f in n["fuentes"]:
        partes.append(f'<li><span class="tipo">{e(TIPO_FUENTE.get(f["tipo"], f["tipo"]))}</span> '
                      f'<a href="{e(f["url"])}" target="_blank" rel="noopener">{e(f["nombre"])}</a></li>')
    partes.append("</ul></div></div></details></article>")
    return "\n".join(partes)


def html_jon(ed):
    v = ed["jon_video"]
    r = ed.get("jon_resumen")
    enlaces = [f'<a href="https://www.youtube.com/watch?v={e(v["id"])}" target="_blank" rel="noopener">Ver el video</a>']
    if v.get("resumen_url"):
        enlaces.append(f'<a href="{e(v["resumen_url"])}" target="_blank" rel="noopener">resumen escrito de Jon</a>')
    partes = ['<section class="caja jon video" id="jon"><strong>Video de Jon Hernández</strong>',
              f'<h2>{e(v["titulo"])}</h2>']
    if r:
        partes.append(f'<p class="intro">{e(r["de_que_trata"])}</p>')
        partes += [f"<p>{e(p)}</p>" for p in r["explicacion"]]
        partes.append("<h3>Puntos clave</h3><ul>")
        for p in r["puntos_clave"]:
            enlace = ""
            if p.get("segundo") is not None:
                enlace = (f' <a href="{e(url_jon(ed, p["segundo"]))}" target="_blank" rel="noopener">'
                          f'({marca(p["segundo"])})</a>')
            partes.append(f'<li>{e(p["texto"])}{enlace}</li>')
        partes.append(f'</ul><p class="nota-base">{e(BASE_JON[r["base"]])}</p>')
    partes.append(f'<p>{" · ".join(enlaces)}</p></section>')
    return "\n".join(partes)


def html_pagina(titulo, cuerpo, descripcion=""):
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<link rel="stylesheet" href="estilo.css">
</head>
<body>
<main>
{cuerpo}
<footer>Resumen armado automáticamente por Claude cada mañana a partir de fuentes verificadas.
Cada noticia indica su nivel de verificación y sus fuentes: ante la duda, leé la fuente.</footer>
</main>
<script src="pagina.js"></script>
</body>
</html>
"""


def html_edicion(ed, anterior, siguiente):
    nav = ['<nav class="nav">']
    nav.append(f'<a href="{anterior}.html">← {e(fecha_larga(anterior).split(" de ")[0])}</a>' if anterior else "<span></span>")
    nav.append('<a href="archivo.html">Archivo</a>')
    nav.append(f'<a href="{siguiente}.html">{e(fecha_larga(siguiente).split(" de ")[0])} →</a>' if siguiente else "<span></span>")
    nav.append("</nav>")
    cab = [f'<header><p class="sobre">Noticias de IA</p><h1>{e(fecha_larga(ed["fecha"]).capitalize())}</h1>',
           f'<p class="intro">{e(ed["intro"])}</p>',
           '<button type="button" id="todo" class="boton">Abrir todas</button></header>']
    notas = [html_noticia(ed, i, n) for i, n in enumerate(ed["noticias"], 1)]
    pie = []
    if ed.get("jon_video"):
        pie.append(html_jon(ed))
    else:
        previa = ultimo_video_jon(ed["fecha"])
        if previa:
            pie.append(f'<section class="caja jon video"><strong>Video de Jon Hernández</strong><p>'
                       f'{e(aviso_sin_video(previa))} <a href="{previa["fecha"]}.html#jon">'
                       f'{e(previa["jon_video"]["titulo"])}</a></p></section>')
    leyenda = "".join(f'<li><span class="chip ver-{k}">{v[0]} {v[1]}</span> {e(v[2])}</li>' for k, v in VERACIDAD.items())
    pie.append(f'<section class="leyenda"><strong>Cómo leer las etiquetas</strong><ul>{leyenda}</ul></section>')
    cuerpo = "\n".join(nav + cab + notas + pie + nav)
    return html_pagina(f"Noticias de IA · {fecha_larga(ed['fecha'])}", cuerpo, ed["intro"])


def html_archivo(ediciones):
    filas = [f'<li><a href="{ed["fecha"]}.html"><strong>{e(fecha_larga(ed["fecha"]).capitalize())}</strong></a>'
             f'<p>{e(ed["intro"])}</p></li>' for ed in reversed(ediciones)]
    cuerpo = ('<header><p class="sobre">Noticias de IA</p><h1>Archivo</h1></header>'
              f'<ul class="archivo">{"".join(filas)}</ul>')
    return html_pagina("Noticias de IA · Archivo", cuerpo)


def construir_sitio():
    if SITIO.exists():
        shutil.rmtree(SITIO)
    SITIO.mkdir(parents=True)
    for nombre in ("estilo.css", "pagina.js"):
        shutil.copy(RAIZ / "sitio" / nombre, SITIO / nombre)
    (SITIO / ".nojekyll").write_text("", encoding="utf-8")

    ediciones = [leer_json(p) for p in sorted(EDICIONES.glob("????-??-??.json"))]
    fechas = [ed["fecha"] for ed in ediciones]
    for k, ed in enumerate(ediciones):
        anterior = fechas[k - 1] if k > 0 else None
        siguiente = fechas[k + 1] if k + 1 < len(fechas) else None
        (SITIO / f"{ed['fecha']}.html").write_text(html_edicion(ed, anterior, siguiente), encoding="utf-8")
    (SITIO / "archivo.html").write_text(html_archivo(ediciones), encoding="utf-8")
    if ediciones:
        ultima = ediciones[-1]
        anterior = fechas[-2] if len(fechas) > 1 else None
        (SITIO / "index.html").write_text(html_edicion(ultima, anterior, None), encoding="utf-8")
    else:
        (SITIO / "index.html").write_text(html_pagina("Noticias de IA", "<h1>Todavía no hay ediciones.</h1>"), encoding="utf-8")
    print(f"Sitio armado en {SITIO} con {len(ediciones)} edición(es).")


def main():
    consola_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitio", action="store_true")
    ap.add_argument("--fecha")
    ap.add_argument("--solo-mensaje", action="store_true")
    ap.add_argument("--base-url", default=os.environ.get("SITIO_URL", "https://USUARIO.github.io/noticias-ia"))
    args = ap.parse_args()
    if args.sitio:
        construir_sitio()
    if args.solo_mensaje:
        ed = leer_json(EDICIONES / f"{args.fecha}.json")
        texto, teclado = mensaje_telegram(ed, args.base_url)
        print(texto)
        print(f"\n--- {len(texto)} caracteres. Botones:")
        for fila in teclado["inline_keyboard"]:
            print("   " + "  |  ".join(f"[{b['text']}]" for b in fila))
        segundo = mensaje_jon(ed)
        if segundo:
            print(f"\n=== Segundo mensaje ===\n{segundo}\n\n--- {len(segundo)} caracteres.")


if __name__ == "__main__":
    main()
