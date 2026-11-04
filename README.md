# Noticias de IA · resumen diario automático

Cada mañana, sin que nadie haga nada, llega un resumen de las noticias de inteligencia artificial
más importantes por **Telegram** y por **mail**. Cada noticia trae un botón "ver más" que abre una
página web con el detalle, las fuentes y, si Jon Hernández habló del tema, el minuto exacto de su video.

## Cómo funciona (horario de Argentina)

| Hora | Quién | Qué hace |
|---|---|---|
| 6:07 | GitHub (`recolectar.yml`) | Lee unas 20 fuentes confiables y el canal de Jon Hernández. Guarda todo en `datos/crudo/`. |
| 6:40 | Claude (rutina en la nube) | Sigue [RUTINA.md](RUTINA.md): elige las 6 a 10 noticias más importantes, las verifica en su fuente original y escribe `ediciones/FECHA.json`. |
| enseguida | GitHub (`publicar.yml`) | Controla la calidad, actualiza la página web y manda el Telegram y el mail. |
| 7:23 y 8:07 | GitHub (`publicar.yml`) | Red de seguridad: si algo no salió, reintenta; si a las 8 no hay edición, manda los titulares sin resumir. |

## Niveles de verificación

- 🟢 **Oficial**: lo anunció la propia empresa u organismo.
- 🔵 **Confirmada**: lo publican al menos dos medios serios independientes.
- 🟠 **Sin confirmar**: una sola fuente o rumor.

## Archivos

- `config/fuentes.json`: lista de fuentes (se puede agregar o quitar).
- `RUTINA.md`: instrucciones que sigue Claude cada mañana.
- `scripts/`: recolectar, validar, publicar (página) y enviar (Telegram y mail). Solo usan Python estándar.
- `sitio/`: estilo de la página. `ediciones/`: una edición por día. `estado/`: qué se envió.

Configuración inicial: ver [CONFIGURACION.md](CONFIGURACION.md).
