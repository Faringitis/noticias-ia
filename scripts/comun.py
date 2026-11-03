"""Funciones compartidas por todos los scripts (solo biblioteca estándar de Python)."""
import datetime as dt
import gzip
import json
import pathlib
import sys
import urllib.request
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config"
CRUDO = RAIZ / "datos" / "crudo"
EDICIONES = RAIZ / "ediciones"
ESTADO = RAIZ / "estado"
SITIO = RAIZ / "_sitio"

# Argentina no usa horario de verano: UTC-3 fijo.
ZONA_AR = dt.timezone(dt.timedelta(hours=-3), "ART")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

AGENTE = "Mozilla/5.0 (compatible; NoticiasIA/1.0; +https://github.com)"


def consola_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def ahora_ar():
    return dt.datetime.now(ZONA_AR)


def hoy_ar():
    return ahora_ar().date().isoformat()


def fecha_larga(iso):
    d = dt.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def descargar(url, timeout=25):
    """Baja una URL y devuelve bytes, descomprimiendo gzip/deflate si hace falta."""
    req = urllib.request.Request(url, headers={
        "User-Agent": AGENTE,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "es,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        datos = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or datos[:2] == b"\x1f\x8b":
        datos = gzip.decompress(datos)
    elif enc == "deflate":
        datos = zlib.decompress(datos)
    return datos


def leer_json(ruta, defecto=None):
    ruta = pathlib.Path(ruta)
    if not ruta.exists():
        return defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_json(ruta, datos):
    ruta = pathlib.Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ediciones_anteriores(antes_de, cantidad=3):
    """Devuelve las últimas `cantidad` ediciones con fecha menor a `antes_de`."""
    archivos = sorted(p for p in EDICIONES.glob("????-??-??.json") if p.stem < antes_de)
    return [leer_json(p) for p in archivos[-cantidad:]]
