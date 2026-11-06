"""Manda la edición del día por Telegram y por mail (lo corre GitHub, no Claude).

Uso:
  python scripts/enviar.py --fecha F            manda la edición F por los canales que falten
  python scripts/enviar.py --respaldo           si a esta hora no hay edición, manda titulares sin resumir
  python scripts/enviar.py --conectar-telegram  le escribe a Santiago su número de chat (configuración inicial)
  python scripts/enviar.py --fecha F --vista-mail RUTA   guarda el mail en un .html para mirarlo (no envía)

Claves (secretos de GitHub, nunca en el código):
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID         → canal Telegram
  MAIL_USUARIO, MAIL_CLAVE_APP, MAIL_DESTINO → canal mail (Gmail con contraseña de aplicación)
Un canal sin sus claves se saltea sin error. En estado/enviados.json se anota qué se mandó,
así nunca llega dos veces lo mismo.
"""
import argparse
import email.message
import json
import os
import smtplib
import sys
import urllib.request

from comun import (CRUDO, EDICIONES, ESTADO, ahora_ar, consola_utf8, fecha_larga,
                   guardar_json, hoy_ar, leer_json)
from publicar import (BASE_JON, VERACIDAD, aviso_sin_video, e, marca, mensaje_jon, mensaje_telegram,
                      ultimo_video_jon, url_jon)

REGISTRO = ESTADO / "enviados.json"


def base_url():
    return os.environ.get("SITIO_URL", "https://USUARIO.github.io/noticias-ia").rstrip("/")


# ------------------------------------------------------------------ Telegram

def telegram(metodo, datos):
    token = os.environ["TELEGRAM_TOKEN"]
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{metodo}",
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        respuesta = json.loads(r.read())
    if not respuesta.get("ok"):
        raise RuntimeError(f"Telegram respondió: {respuesta.get('description')}")
    return respuesta["result"]


def mandar_telegram(texto, teclado=None):
    datos = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": texto,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    if teclado:
        datos["reply_markup"] = teclado
    telegram("sendMessage", datos)


def conectar_telegram():
    """Busca el último chat que le escribió al bot y le contesta con su número de chat."""
    updates = telegram("getUpdates", {"timeout": 0})
    chats = [u["message"]["chat"] for u in updates if "message" in u]
    if not chats:
        sys.exit("No encontré mensajes. Abrí tu bot en Telegram, mandale 'hola' y volvé a correr esto.")
    chat = chats[-1]
    telegram("sendMessage", {
        "chat_id": chat["id"],
        "text": ("¡Conectado! 🎉\n\nTu número de chat es:\n\n" + str(chat["id"]) +
                 "\n\nCopialo y guardalo en GitHub como el secreto TELEGRAM_CHAT_ID."),
    })
    print("Listo: te mandé tu número de chat por Telegram (no se muestra acá por privacidad).")


# ------------------------------------------------------------------ Mail

def html_mail(ed):
    pagina = f"{base_url()}/{ed['fecha']}.html"
    filas = []
    for i, n in enumerate(ed["noticias"], 1):
        emoji, etiqueta, _ = VERACIDAD[n["veracidad"]]
        filas.append(f"""
<div style="padding:14px 0;border-top:1px solid #e3e1d9">
  <div style="font-size:12px;color:#5f5e58">{i} · {e(n['categoria'])} · {emoji} {e(etiqueta)}</div>
  <div style="font-size:17px;font-weight:700;line-height:1.3;margin:4px 0 6px;color:#1d1d1b">{e(n['titulo'])}</div>
  <div style="font-size:15px;line-height:1.5;color:#3d3d39">{e(n['breve'])}</div>
  <div style="margin-top:6px"><a href="{e(pagina)}#n{i}" style="color:#3b5bdb;font-size:14px;font-weight:600;text-decoration:none">Ver más →</a></div>
</div>""")
    jon = ""
    if ed.get("jon_video"):
        v = ed["jon_video"]
        r = ed.get("jon_resumen")
        cuerpo_jon = ""
        if r:
            parrafos = "".join(f'<p style="margin:10px 0;line-height:1.5">{e(p)}</p>' for p in r["explicacion"])
            puntos = ""
            for p in r["puntos_clave"]:
                enlace = ""
                if p.get("segundo") is not None:
                    enlace = (f' <a href="{e(url_jon(ed, p["segundo"]))}" style="color:#3b5bdb">'
                              f'({marca(p["segundo"])})</a>')
                puntos += f'<li style="margin:5px 0">{e(p["texto"])}{enlace}</li>'
            cuerpo_jon = (f'<p style="margin:10px 0;font-weight:600;line-height:1.5">{e(r["de_que_trata"])}</p>{parrafos}'
                          f'<div style="font-weight:700;margin-top:12px">Puntos clave</div>'
                          f'<ul style="margin:6px 0;padding-left:20px;line-height:1.45">{puntos}</ul>'
                          f'<div style="font-size:12px;color:#5f5e58">{e(BASE_JON[r["base"]])}</div>')
        jon = (f'<div style="padding:12px 14px;background:#fff4e6;border-radius:10px;font-size:15px;color:#1d1d1b;margin-top:6px">'
               f'📺 <strong>Video de Jon Hernández:</strong> <a href="https://www.youtube.com/watch?v={e(v["id"])}" '
               f'style="color:#3b5bdb">{e(v["titulo"])}</a>{cuerpo_jon}</div>')
    elif ultimo_video_jon(ed["fecha"]):
        previa = ultimo_video_jon(ed["fecha"])
        jon = (f'<div style="padding:12px 14px;background:#fff4e6;border-radius:10px;font-size:15px;color:#1d1d1b;margin-top:6px">'
               f'📺 {e(aviso_sin_video(previa))} <a href="{e(base_url())}/{previa["fecha"]}.html#jon" '
               f'style="color:#3b5bdb">{e(previa["jon_video"]["titulo"])}</a></div>')
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f6f5f1">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f5f1"><tr><td align="center" style="padding:12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;border-radius:14px">
<tr><td style="padding:20px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;text-align:left">
<div style="padding-bottom:10px">
  <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#5f5e58;font-weight:600">Noticias de IA</div>
  <div style="font-size:22px;font-weight:700;color:#1d1d1b;margin:2px 0 8px">{e(fecha_larga(ed['fecha']).capitalize())}</div>
  <div style="font-size:16px;line-height:1.5;color:#5f5e58">{e(ed['intro'])}</div>
</div>
{''.join(filas)}
{jon}
<div style="padding-top:16px;font-size:12px;color:#5f5e58">
  🟢 oficial · 🔵 confirmada por 2 medios · 🟠 sin confirmar<br>
  <a href="{e(pagina)}" style="color:#3b5bdb">Ver la edición completa en la web</a>
</div>
</td></tr></table></td></tr></table></body></html>"""


def texto_mail(ed):
    pagina = f"{base_url()}/{ed['fecha']}.html"
    partes = [f"Noticias de IA · {fecha_larga(ed['fecha'])}", "", ed["intro"], ""]
    for i, n in enumerate(ed["noticias"], 1):
        partes += [f"{i}. {n['titulo']}", n["breve"], f"Ver más: {pagina}#n{i}", ""]
    r = ed.get("jon_resumen")
    if r and ed.get("jon_video"):
        partes += [f"Video de Jon Hernández: {ed['jon_video']['titulo']}",
                   f"https://www.youtube.com/watch?v={ed['jon_video']['id']}", "", r["de_que_trata"], ""]
        partes += [x for p in r["explicacion"] for x in (p, "")]
        partes += ["Puntos clave:"] + [f"- {p['texto']}" for p in r["puntos_clave"]]
    elif ultimo_video_jon(ed["fecha"]):
        previa = ultimo_video_jon(ed["fecha"])
        partes += [aviso_sin_video(previa), previa["jon_video"]["titulo"],
                   f"{base_url()}/{previa['fecha']}.html#jon"]
    return "\n".join(partes)


def mandar_mail(asunto, texto, html_cuerpo=None):
    usuario = os.environ["MAIL_USUARIO"]
    msg = email.message.EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = f"Noticias de IA <{usuario}>"
    msg["To"] = os.environ.get("MAIL_DESTINO") or usuario
    msg.set_content(texto)
    if html_cuerpo:
        msg.add_alternative(html_cuerpo, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(usuario, os.environ["MAIL_CLAVE_APP"])
        s.send_message(msg)


# ------------------------------------------------------------------ Envíos

def canales():
    c = []
    if os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        c.append("telegram")
    if os.environ.get("MAIL_USUARIO") and os.environ.get("MAIL_CLAVE_APP"):
        c.append("mail")
    return c


def enviar_edicion(fecha):
    ed = leer_json(EDICIONES / f"{fecha}.json")
    if not ed:
        print(f"No hay edición para {fecha}.")
        return
    registro = leer_json(REGISTRO, {})
    hecho = registro.setdefault(fecha, {})
    fallas = []
    envios = canales()
    if "telegram" in envios and mensaje_jon(ed):
        envios.insert(1, "telegram_jon")
    for canal in envios:
        if canal in hecho:
            print(f"{canal}: ya se había mandado.")
            continue
        try:
            if canal == "telegram":
                texto, teclado = mensaje_telegram(ed, base_url())
                mandar_telegram(texto, teclado)
            elif canal == "telegram_jon":
                mandar_telegram(mensaje_jon(ed))
            else:
                principal = ed["noticias"][0]["titulo_corto"]
                mandar_mail(f"🤖 Noticias de IA · {fecha_larga(fecha).rsplit(' de ', 1)[0]} · {principal}",
                            texto_mail(ed), html_mail(ed))
            hecho[canal] = ahora_ar().isoformat(timespec="minutes")
            print(f"{canal}: enviado.")
        except Exception as ex:
            fallas.append(canal)
            print(f"{canal}: FALLÓ → {type(ex).__name__}: {ex}")
    guardar_json(REGISTRO, registro)
    if fallas:
        sys.exit(1)


def enviar_respaldo():
    fecha = hoy_ar()
    if (EDICIONES / f"{fecha}.json").exists():
        print("Hay edición: no hace falta respaldo.")
        return
    registro = leer_json(REGISTRO, {})
    hecho = registro.setdefault(fecha, {})
    if hecho.get("respaldo"):
        print("El respaldo ya se mandó hoy.")
        return
    crudo = leer_json(CRUDO / f"{fecha}.json", {})
    notas = [n for n in crudo.get("notas", []) if n["nivel"] in ("oficial", "medio")][:8]
    lineas = ["⚠️ <b>Hoy no se pudo armar el resumen.</b>",
              "Te dejo los titulares de las fuentes principales, sin resumir:", ""]
    for n in notas:
        lineas.append(f"• <a href=\"{e(n['url'])}\">{e(n['titulo'])}</a> <i>({e(n['fuente'])})</i>")
    for v in crudo.get("jon_videos", []):
        if v.get("es_noticias") and not v.get("ya_cubierto"):
            lineas.append(f"\n📺 Jon Hernández: <a href=\"{e(v['url'])}\">{e(v['titulo'])}</a>")
    if not notas:
        lineas.append("(Tampoco se pudieron leer las fuentes. Mañana debería volver a la normalidad.)")
    texto = "\n".join(lineas)
    for canal in canales():
        try:
            if canal == "telegram":
                mandar_telegram(texto)
            else:
                plano = texto.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                mandar_mail("⚠️ Noticias de IA: hoy solo titulares", plano, texto.replace("\n", "<br>"))
            print(f"respaldo por {canal}: enviado.")
        except Exception as ex:
            print(f"respaldo por {canal}: FALLÓ → {type(ex).__name__}: {ex}")
    hecho["respaldo"] = ahora_ar().isoformat(timespec="minutes")
    guardar_json(REGISTRO, registro)


def main():
    consola_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha")
    ap.add_argument("--respaldo", action="store_true")
    ap.add_argument("--conectar-telegram", action="store_true")
    ap.add_argument("--vista-mail")
    args = ap.parse_args()
    if args.conectar_telegram:
        conectar_telegram()
    elif args.respaldo:
        enviar_respaldo()
    elif args.vista_mail:
        ed = leer_json(EDICIONES / f"{args.fecha}.json")
        with open(args.vista_mail, "w", encoding="utf-8") as f:
            f.write(html_mail(ed))
        print(f"Vista del mail guardada en {args.vista_mail}")
    elif args.fecha:
        enviar_edicion(args.fecha)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
