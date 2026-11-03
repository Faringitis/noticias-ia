"""Control de calidad de una edición antes de publicarla.

Uso: python scripts/validar.py AAAA-MM-DD   (o la ruta a un .json)
Sale con código 1 si hay errores; las advertencias no frenan la publicación.
"""
import pathlib
import re
import sys
import urllib.parse

from comun import EDICIONES, consola_utf8, ediciones_anteriores, leer_json

CATEGORIAS = {"Modelos", "Herramientas", "Empresas", "Investigación", "Regulación",
              "Trabajo y sociedad", "Hardware", "Seguridad"}
VERACIDAD = {"oficial", "confirmada", "sin_confirmar"}
TIPOS_FUENTE = {"oficial", "medio", "especialista", "jon"}


def dominio(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def validar(ed, nombre_archivo=None):
    errores, avisos = [], []
    E, A = errores.append, avisos.append

    if not isinstance(ed, dict):
        return ["La edición no es un objeto JSON."], []
    fecha = ed.get("fecha")
    if not isinstance(fecha, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        E("'fecha' falta o no tiene formato AAAA-MM-DD.")
    elif nombre_archivo and nombre_archivo != fecha:
        E(f"El archivo se llama {nombre_archivo}.json pero 'fecha' dice {fecha}.")

    intro = ed.get("intro")
    if not isinstance(intro, str) or not intro.strip():
        E("'intro' falta o está vacía.")
    elif len(intro) > 280:
        E(f"'intro' tiene {len(intro)} caracteres (máx. 280).")

    jon = ed.get("jon_video")
    if jon is not None:
        if not isinstance(jon, dict) or not jon.get("id") or not jon.get("titulo"):
            E("'jon_video' debe ser null o tener al menos 'id' y 'titulo'.")

    noticias = ed.get("noticias")
    if not isinstance(noticias, list) or not noticias:
        return errores + ["'noticias' falta o está vacía."], avisos
    if not 3 <= len(noticias) <= 12:
        E(f"Hay {len(noticias)} noticias (tiene que haber entre 3 y 12).")
    elif not 6 <= len(noticias) <= 10:
        A(f"Hay {len(noticias)} noticias (lo ideal es entre 6 y 10).")

    for i, n in enumerate(noticias, 1):
        p = f"Noticia {i}"
        if not isinstance(n, dict):
            E(f"{p}: no es un objeto.")
            continue
        for campo, maximo in (("titulo", 120), ("titulo_corto", 28), ("breve", 260), ("por_que_importa", 400)):
            v = n.get(campo)
            if not isinstance(v, str) or not v.strip():
                E(f"{p}: falta '{campo}'.")
            elif len(v) > maximo:
                E(f"{p}: '{campo}' tiene {len(v)} caracteres (máx. {maximo}).")
        if n.get("categoria") not in CATEGORIAS:
            E(f"{p}: 'categoria' inválida ({n.get('categoria')!r}). Opciones: {', '.join(sorted(CATEGORIAS))}.")
        if n.get("veracidad") not in VERACIDAD:
            E(f"{p}: 'veracidad' inválida ({n.get('veracidad')!r}). Opciones: {', '.join(sorted(VERACIDAD))}.")

        detalle = n.get("detalle")
        if not isinstance(detalle, list) or not all(isinstance(x, str) and x.strip() for x in detalle):
            E(f"{p}: 'detalle' tiene que ser una lista de párrafos (texto).")
        else:
            if not 2 <= len(detalle) <= 5:
                E(f"{p}: 'detalle' tiene {len(detalle)} párrafos (entre 2 y 5).")
            palabras = sum(len(x.split()) for x in detalle)
            if not 80 <= palabras <= 400:
                A(f"{p}: 'detalle' tiene {palabras} palabras (ideal 120 a 300).")

        if n.get("jon_opina") is not None and not isinstance(n.get("jon_opina"), str):
            E(f"{p}: 'jon_opina' tiene que ser texto o null.")
        seg = n.get("jon_segundo")
        if seg is not None:
            if not isinstance(seg, int) or isinstance(seg, bool) or seg < 0:
                E(f"{p}: 'jon_segundo' tiene que ser un entero ≥ 0 o null.")
            elif not jon:
                E(f"{p}: tiene 'jon_segundo' pero la edición no tiene 'jon_video'.")

        fuentes = n.get("fuentes")
        if not isinstance(fuentes, list) or not fuentes:
            E(f"{p}: necesita al menos una fuente.")
            continue
        dominios = set()
        for j, f in enumerate(fuentes, 1):
            if not isinstance(f, dict) or not f.get("nombre") or not f.get("url"):
                E(f"{p}, fuente {j}: necesita 'nombre' y 'url'.")
                continue
            url = f["url"]
            if not url.startswith("https://") and not url.startswith("http://"):
                E(f"{p}, fuente {j}: la URL no empieza con http(s)://.")
            if "news.google.com" in url:
                E(f"{p}, fuente {j}: no citar links de Google Noticias; buscar la URL original.")
            if f.get("tipo") not in TIPOS_FUENTE:
                E(f"{p}, fuente {j}: 'tipo' inválido ({f.get('tipo')!r}).")
            if f.get("tipo") != "jon":
                dominios.add(dominio(url))
        tipos = [f.get("tipo") for f in fuentes if isinstance(f, dict)]
        if n.get("veracidad") == "oficial" and "oficial" not in tipos:
            E(f"{p}: dice 'oficial' pero ninguna fuente es de tipo 'oficial'.")
        if n.get("veracidad") == "confirmada" and len(dominios) < 2:
            E(f"{p}: dice 'confirmada' pero no tiene 2 fuentes de sitios distintos.")

    # Repeticiones con ediciones anteriores (solo aviso).
    if isinstance(fecha, str):
        previos = {re.sub(r"\W+", "", x.get("titulo", "").lower())
                   for e in ediciones_anteriores(fecha, 3) for x in e.get("noticias", [])}
        for i, n in enumerate(noticias, 1):
            if isinstance(n, dict) and re.sub(r"\W+", "", str(n.get("titulo", "")).lower()) in previos:
                A(f"Noticia {i}: el título es igual a uno de una edición anterior.")

    # El mensaje de Telegram tiene que entrar en un solo mensaje.
    if not errores:
        from publicar import mensaje_telegram
        texto, _ = mensaje_telegram(ed, "https://ejemplo.github.io/noticias-ia")
        if len(texto) > 4096:
            E(f"El mensaje de Telegram queda de {len(texto)} caracteres (máx. 4096): acortá 'breve' o 'intro'.")
    return errores, avisos


def main():
    consola_utf8()
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    arg = sys.argv[1]
    ruta = pathlib.Path(arg) if arg.endswith(".json") else EDICIONES / f"{arg}.json"
    if not ruta.exists():
        print(f"ERROR: no existe {ruta}")
        sys.exit(1)
    try:
        ed = leer_json(ruta)
    except ValueError as e:
        print(f"ERROR: el JSON está mal formado: {e}")
        sys.exit(1)
    errores, avisos = validar(ed, ruta.stem)
    for a in avisos:
        print("AVISO:", a)
    for e in errores:
        print("ERROR:", e)
    if errores:
        print(f"\n{len(errores)} error(es). Corregir y volver a validar.")
        sys.exit(1)
    print("OK: la edición está lista.")


if __name__ == "__main__":
    main()
