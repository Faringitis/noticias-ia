# Configuración inicial (una sola vez)

Son unos 15 minutos. Las claves las cargás **vos** directamente en GitHub: Claude nunca las ve.

## 1. Crear el bot de Telegram (3 min)

1. En Telegram, buscá **@BotFather** (tiene tilde azul) y escribile `/newbot`.
2. Te pide un nombre (por ejemplo `Noticias IA Santiago`) y un usuario que termine en `bot`
   (por ejemplo `noticias_ia_santi_bot`).
3. Te responde con un **token** (una clave larga tipo `123456:ABC...`). Copialo y guardalo un momento.
4. Tocá el link a tu bot que te da BotFather, apretá **Iniciar** y mandale `hola`.

## 2. Crear la contraseña de aplicación de Gmail (3 min)

Sirve para que GitHub te mande el mail desde tu Gmail sin usar tu contraseña real.

1. Entrá a <https://myaccount.google.com/apppasswords> (si te dice que no está disponible, primero
   activá la **Verificación en dos pasos** en <https://myaccount.google.com/security>).
2. Nombre de la app: `Noticias IA`. Tocá **Crear**.
3. Te muestra una clave de 16 letras. Copiala (los espacios no importan).
   Se puede borrar en cualquier momento desde esa misma página y el envío por mail deja de funcionar.

## 3. Crear el repositorio en GitHub (2 min)

1. Entrá a <https://github.com/new>.
2. Nombre: `noticias-ia`. Visibilidad: **Public** (necesario para la página web gratis; solo
   contiene noticias públicas, nada personal). **No** marques "Add a README".
3. Tocá **Create repository** y avisale a Claude: él sube los archivos (puede que se abra el
   navegador para que autorices con tu cuenta de GitHub).

## 4. Cargar las claves en GitHub (3 min)

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
Creá uno por uno (el nombre tiene que ser exacto):

| Nombre | Valor |
|---|---|
| `TELEGRAM_TOKEN` | el token del paso 1 |
| `MAIL_USUARIO` | tu dirección de Gmail |
| `MAIL_CLAVE_APP` | la clave de 16 letras del paso 2 |
| `MAIL_DESTINO` | (opcional) otra dirección donde recibirlo; si no lo creás, llega a tu Gmail |

## 5. Activar la página web (1 min)

**Settings → Pages → Build and deployment → Source: GitHub Actions.**

## 6. Conectar Telegram (2 min)

1. Pestaña **Actions → "0 · Conectar Telegram" → Run workflow**.
2. A los segundos tu bot te escribe tu **número de chat**.
3. Guardalo como un secreto más llamado `TELEGRAM_CHAT_ID` (como en el paso 4).

## 7. La rutina de Claude

Este paso lo hace Claude con vos: crea la rutina en la nube que todos los días a las 6:40
lee las fuentes, verifica y escribe la edición.

## 8. Prueba

**Actions → "2 · Publicar y enviar" → Run workflow**, con fecha `2026-11-03` y "reenviar" marcado.
Te tiene que llegar el Telegram y el mail con la edición de prueba.

---

**Para apagarlo todo:** en Actions, desactivá los workflows, y en Claude, pausá la rutina.
**Para cambiar la hora:** decíselo a Claude (hay que mover la rutina y los horarios de GitHub juntos).
