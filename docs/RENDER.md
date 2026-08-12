# Mudanza del captador a Render

Todo por navegador. No hace falta terminal en ningún paso.

---

## Antes: crear el bot de Telegram (5 min)

Las alertas van por Telegram porque DigitalOcean —y casi cualquier hosting—
bloquea el envío de correo desde el servidor.

1. En Telegram, busca **@BotFather** y ábrelo
2. Manda `/newbot`
3. Te pide un nombre (ej: `Captador LeadMaster`) y un usuario que termine en
   `bot` (ej: `captador_leadmaster_bot`)
4. Te devuelve un **token** tipo `8123456789:AAH...`. Guárdalo.
5. Busca tu bot por ese usuario, ábrelo y mándale cualquier mensaje (`hola`).
   **Este paso es obligatorio**: Telegram no deja que un bot escriba primero.
6. Abre esta dirección en el navegador, con tu token:

   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```

   Busca `"chat":{"id":123456789` — ese número es tu **chat id**.

Con el token y el chat id sigues.

---

## Paso 1 — Subir el código a GitHub

1. Entra a [github.com](https://github.com) → botón **New** (repositorio nuevo)
2. Nombre: `captador-leads`
3. Marca **Private** ← importante
4. **Create repository**
5. En la página que sigue, clic en **uploading an existing file**
6. Arrastra estos archivos de la carpeta `procesador` de tu Mac:
   - `main.py`
   - `Dockerfile`
   - `requirements.txt`
   - `.env.example`
   - `README.md`
7. **Commit changes**

> **Nunca subas el archivo `.env`.** Las credenciales van en el panel de Render,
> no en el repositorio. El `.gitignore` ya lo impide, pero al subir a mano hay
> que fijarse.

## Paso 2 — Crear el servicio en Render

1. [render.com](https://render.com) → entra con GitHub
2. **New** → **Background Worker**
3. Conecta el repositorio `captador-leads`
4. Configura:
   - **Language / Runtime**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Instance Type**: `Starter` (US$7/mes, 512 MB)
   - **Region**: Ohio o Virginia (cerca de México)

> No es un *Web Service*: el captador no atiende peticiones, solo trabaja en
> segundo plano. Si eliges Web Service, Render lo va a matar por no responder
> en un puerto.

## Paso 3 — Las credenciales

En **Environment** → **Add Environment Variable**, una por una:

| Clave | Valor |
|---|---|
| `IMAP_HOST` | `imap.gmail.com` |
| `IMAP_USER` | `capturasremaxmid@gmail.com` |
| `IMAP_PASS` | la contraseña de aplicación de Google (16 caracteres, sin espacios) |
| `CARPETA_REVISAR` | `REVISAR` |
| `PROVEEDOR` | `openai` |
| `OPENAI_API_KEY` | tu llave de OpenAI |
| `GHL_TOKEN` | el token de GHL |
| `GHL_LOCATION_ID` | `rkLMMyinmQJt6JTrZ8vE` |
| `GHL_TAG` | `Creado_por_leadmaster` |
| `MAX_INTENTOS` | `3` |
| `TELEGRAM_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | tu chat id |
| `ALERTA_MINUTOS` | `30` |

**Create Background Worker**. Tarda 2–3 minutos en construir.

## Paso 4 — Comprobar

Pestaña **Logs** del servicio. Debe aparecer:

```
captador iniciado | buzon=capturasremaxmid@gmail.com | modelo=gpt-4o-mini
conectado, esperando correo
```

## Paso 5 — Apagar el del droplet ⚠️

**Este paso no se salta.** Si los dos quedan corriendo, ambos leen el mismo
buzón, compiten por los mismos correos y duplican notas en GHL.

Entra al droplet una última vez:

```bash
ssh root@147.182.209.15
```

```bash
cd /opt/captador && docker compose down
```

Evolution API no se toca, sigue corriendo igual.

## Paso 6 — Prueba final

Reenvía un correo y mira los logs **en Render**. Debe salir la línea `OK`.

---

## De aquí en adelante

| Qué quieres hacer | Cómo |
|---|---|
| Ver los leads que entraron | pestaña **Logs** en Render |
| Cambiar el token de GHL | **Environment** → editar el valor → guardar |
| Cambiar el prompt o agregar claves de asesores | editar `main.py` en GitHub (lápiz ✏️) → *Commit* → Render redespliega solo |
| Reiniciar | botón **Manual Deploy** → *Restart service* |

Sin `ssh`, sin `nano`, sin `scp`, sin `docker`.

---

## Por qué Evolution API se queda en el droplet

Podría correr en Render, pero saldría más caro y más frágil:

| | Droplet (hoy) | Render |
|---|---|---|
| Evolution API | incluido | Web Service US$7 |
| Postgres | incluido | US$6+ |
| Redis | incluido | aparte |
| Disco persistente | incluido | aparte |
| **Total** | **US$12** | **US$20+** |

Y hay un problema de fondo: Evolution API guarda la **sesión de WhatsApp**. Es
un servicio con estado, y cada redespliegue de Render arriesga que se pierda esa
sesión y toque escanear el QR de nuevo.

El captador es lo contrario: no guarda nada, su estado vive en las banderas de
IMAP. Por eso se muda sin problema.

**La regla:** lo que guarda estado se queda en el VPS; lo que no guarda nada
puede vivir en un PaaS. Cada cosa donde le sirve.
