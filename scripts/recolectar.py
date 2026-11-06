"""Paso 1 de cada mañana: junta la materia prima.

Lee los feeds de config/fuentes.json y el canal de Jon Hernández (con su
link a su "Resumen Plaud" escrito, que Claude lee después con su propia
herramienta web, y los links a las fuentes originales) y guarda todo en
datos/crudo/AAAA-MM-DD.json. No resume ni decide nada: eso lo hace Claude.

Uso: python scripts/recolectar.py [--fecha AAAA-MM-DD]
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import html
import re
import xml.etree.ElementTree as ET

from comun import (CONFIG, CRUDO, ahora_ar, consola_utf8, descargar,
                   ediciones_anteriores, guardar_json, hoy_ar, leer_json)

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
DC = "{http://purl.org/dc/elements/1.1/}"


def limpiar(texto, largo=None):
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))
    texto = re.sub(r"\s+", " ", texto).strip()
    if largo and len(texto) > largo:
        texto = texto[:largo].rsplit(" ", 1)[0] + "…"
    return texto


def leer_fecha(texto):
    if not texto:
        return None
    texto = texto.strip()
    try:
        d = email.utils.parsedate_to_datetime(texto)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def primero(elem, *etiquetas):
    for e in etiquetas:
        x = elem.find(e)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def items_de_feed(datos):
    """Convierte un feed RSS o Atom en una lista de dicts simples."""
    raiz = ET.fromstring(datos)
    salida = []
    for it in raiz.iter("item"):
        salida.append({
            "titulo": primero(it, "title"),
            "url": primero(it, "link"),
            "fecha": leer_fecha(primero(it, "pubDate", DC + "date")),
            "resumen": primero(it, "description", "{http://purl.org/rss/1.0/modules/content/}encoded"),
            "medio": primero(it, "source"),
        })
    for en in raiz.iter(ATOM + "entry"):
        url = ""
        for ln in en.findall(ATOM + "link"):
            if ln.get("rel", "alternate") == "alternate":
                url = ln.get("href", "")
                break
        salida.append({
            "titulo": primero(en, ATOM + "title"),
            "url": url,
            "fecha": leer_fecha(primero(en, ATOM + "published", ATOM + "updated")),
            "resumen": primero(en, ATOM + "summary", ATOM + "content"),
            "medio": "",
        })
    return salida


def habla_de_ia(texto, palabras):
    t = f" {texto.lower()} "
    return any(p in t for p in palabras)


def leer_fuente(fuente, desde, palabras, palabras_ing):
    if fuente.get("ventana_horas"):
        desde = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=fuente["ventana_horas"])
    datos = descargar(fuente["url"])
    notas = []
    for it in items_de_feed(datos):
        if not it["fecha"] or it["fecha"] < desde or not it["titulo"]:
            continue
        titulo = limpiar(it["titulo"])
        medio = limpiar(it["medio"])
        if fuente.get("google_news") and medio and titulo.endswith(" - " + medio):
            titulo = titulo[: -len(medio) - 3]
        resumen = "" if fuente.get("google_news") else limpiar(it["resumen"], 500)
        if fuente.get("filtrar_ia") and not habla_de_ia(f"{titulo} {resumen}", palabras):
            continue
        if fuente.get("filtrar_ing") and not habla_de_ia(f"{titulo} {resumen}", palabras_ing):
            continue
        nota = {
            "fuente": fuente["nombre"],
            "nivel": fuente["nivel"],
            "titulo": titulo,
            "url": it["url"],
            "fecha_utc": it["fecha"].astimezone(dt.timezone.utc).isoformat(timespec="minutes"),
            "resumen": resumen,
        }
        if fuente.get("seccion"):
            nota["seccion"] = fuente["seccion"]
        if fuente.get("google_news"):
            nota["medio"] = medio
            nota["aviso"] = "Link de Google Noticias: buscar la URL original antes de citar."
        notas.append(nota)
    notas.sort(key=lambda n: n["fecha_utc"], reverse=True)
    return notas[: fuente.get("max_notas", 40)]


# ---------------------------------------------------------------- Jon Hernández

def segundos(marca):
    partes = [int(p) for p in marca.split(":")]
    total = 0
    for p in partes:
        total = total * 60 + p
    return total


def analizar_descripcion(desc):
    """Saca de la descripción del video: link al Resumen Plaud, fuentes y minutos."""
    resumen_url = None
    m = re.search(r"Resumen Plaud:\s*(https?://\S+)", desc)
    if m:
        resumen_url = m.group(1)

    links, marcas, seccion = [], [], None
    for linea in desc.splitlines():
        l = linea.strip()
        if re.match(r"^[▷►]\s*Links de inter", l):
            seccion = "links"
            continue
        if re.match(r"^[▷►]\s*Timestamps", l):
            seccion = "marcas"
            continue
        if l.startswith(("▷", "►", "●", "___")):
            seccion = None
            continue
        if seccion == "links":
            m = re.match(r"^(.*?):\s*(https?://\S+)$", l)
            if m:
                links.append({"texto": m.group(1).strip(), "url": m.group(2)})
        elif seccion == "marcas":
            m = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*:?\s*(.+)$", l)
            if m:
                marcas.append({"segundo": segundos(m.group(1)), "marca": m.group(1), "tema": m.group(2).strip()})
    return resumen_url, links, marcas


def leer_jon(cfg, fecha):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cfg['channel_id']}"
    raiz = ET.fromstring(descargar(url))
    desde = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=cfg["ventana_horas"])
    cubiertos = {(e.get("jon_video") or {}).get("id") for e in ediciones_anteriores(fecha, 7)}

    videos = []
    for en in raiz.findall(ATOM + "entry"):
        enlace = en.find(ATOM + "link").get("href", "")
        if "/shorts/" in enlace:
            continue
        publicado = leer_fecha(primero(en, ATOM + "published"))
        if not publicado or publicado < desde:
            continue
        vid = primero(en, YT + "videoId")
        desc = primero(en, MEDIA + "group/" + MEDIA + "description")
        resumen_url, links, marcas = analizar_descripcion(desc)
        video = {
            "id": vid,
            "titulo": primero(en, ATOM + "title"),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "publicado_utc": publicado.astimezone(dt.timezone.utc).isoformat(timespec="minutes"),
            "es_noticias": "NOTICIAS" in primero(en, ATOM + "title").upper(),
            "ya_cubierto": vid in cubiertos,
            "minutos": marcas,
            "links_fuentes": links,
            "resumen_plaud_url": resumen_url,
        }
        # Primer párrafo de la descripción (el "copete" que escribe Jon), sin publicidad.
        parrafos = [x.strip() for x in desc.split("\n\n") if x.strip()]
        video["copete"] = next((x for x in parrafos if "http" not in x and len(x) > 80), "")[:1500]
        if not resumen_url:
            # Sin resumen escrito de Jon, la descripción es el único texto del video.
            video["descripcion"] = desc[:4000]
        videos.append(video)
    return videos


def main():
    consola_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", default=hoy_ar())
    args = ap.parse_args()

    cfg = leer_json(CONFIG / "fuentes.json")
    desde = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=cfg["ventana_horas"])
    palabras = [p.lower() for p in cfg["palabras_ia"]]
    palabras_ing = [p.lower() for p in cfg["palabras_ingenieria"]]

    notas, errores, resumen_fuentes = [], [], []
    with cf.ThreadPoolExecutor(8) as ex:
        tareas = {ex.submit(leer_fuente, f, desde, palabras, palabras_ing): f for f in cfg["feeds"]}
        for t in cf.as_completed(tareas):
            f = tareas[t]
            try:
                r = t.result()
                notas.extend(r)
                resumen_fuentes.append(f"{f['nombre']}: {len(r)}")
            except Exception as e:
                errores.append({"fuente": f["nombre"], "error": f"{type(e).__name__}: {e}"[:200]})

    # Sin duplicados (misma URL o mismo título).
    vistos, unicas = set(), []
    for n in sorted(notas, key=lambda n: n["fecha_utc"], reverse=True):
        clave_t = re.sub(r"\W+", "", n["titulo"].lower())
        if n["url"] in vistos or clave_t in vistos:
            continue
        vistos.update({n["url"], clave_t})
        unicas.append(n)

    orden = {"oficial": 0, "medio": 1, "especialista": 2, "espanol": 3}
    unicas.sort(key=lambda n: (orden.get(n["nivel"], 9), n["fuente"], n["fecha_utc"]))

    try:
        videos = leer_jon(cfg["youtube_jon"], args.fecha)
    except Exception as e:
        videos = []
        errores.append({"fuente": "YouTube Jon Hernández", "error": f"{type(e).__name__}: {e}"[:200]})

    salida = {
        "fecha": args.fecha,
        "generado": ahora_ar().isoformat(timespec="minutes"),
        "ventana_horas": cfg["ventana_horas"],
        "jon_videos": videos,
        "notas": [n for n in unicas if not n.get("seccion")],
        "notas_ingenieria": [n for n in unicas if n.get("seccion") == "ingenieria"],
        "errores": errores,
    }
    destino = CRUDO / f"{args.fecha}.json"
    guardar_json(destino, salida)
    print(f"Guardado {destino.name}: {len(unicas)} notas, {len(videos)} videos de Jon, {len(errores)} errores")
    print("Por fuente:", ", ".join(sorted(resumen_fuentes)))
    for e in errores:
        print("  ERROR", e["fuente"], "→", e["error"])


if __name__ == "__main__":
    main()
