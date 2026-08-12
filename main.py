"""
Captador de leads inmobiliarios: Gmail -> Claude -> GoHighLevel.

Escucha el buzon por IMAP IDLE, procesa cada correo nuevo y crea el contacto
en GHL. No guarda nada: el estado vive en las banderas del propio IMAP.

  correo sin leer  ->  procesado ok    ->  marcado como leido
                   ->  fallo temporal  ->  sigue sin leer, se reintenta
                   ->  fallo definitivo->  movido a la etiqueta REVISAR
"""

import json
import logging
import os
import re
import signal
import smtplib
import sys
import time
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage

import requests
from imapclient import IMAPClient

# --------------------------------------------------------------------------
# Configuracion
# --------------------------------------------------------------------------

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ["IMAP_USER"]
IMAP_PASS = os.environ["IMAP_PASS"]  # contrasena de aplicacion de Google
CARPETA_REVISAR = os.environ.get("CARPETA_REVISAR", "REVISAR")

# "openai" o "anthropic". El trabajo es el mismo; cambia solo quien lo hace.
PROVEEDOR = os.environ.get("PROVEEDOR", "openai").strip().lower()
MODELO = os.environ.get("MODELO") or (
    "gpt-4o-mini" if PROVEEDOR == "openai" else "claude-haiku-4-5-20251001"
)

GHL_TOKEN = os.environ["GHL_TOKEN"]
GHL_LOCATION_ID = os.environ["GHL_LOCATION_ID"]
GHL_BASE = "https://services.leadconnectorhq.com"
ETIQUETA = os.environ.get("GHL_TAG", "Creado_por_leadmaster")

# IDs de los campos personalizados de la sub-cuenta. Se obtienen con:
#   GET /locations/<locationId>/customFields?model=contact
CF_CLAVE_INTERNA = os.environ.get("CF_CLAVE_INTERNA", "MuUq6ZwtqXWLoJoOrkZ4")
CF_PROYECTO = os.environ.get("CF_PROYECTO", "hMkSTQHqez2nkPqb3saH")

# Cuantas veces se reintenta un correo antes de mandarlo a REVISAR.
MAX_INTENTOS = int(os.environ.get("MAX_INTENTOS", "3"))

# Alertas por Telegram. Va por HTTPS (443), que es lo unico que sirve aqui:
# DigitalOcean bloquea los puertos SMTP (25/465/587) en todos sus droplets,
# asi que mandar correo desde el servidor no es posible.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Alertas por correo. Solo funciona si el servidor tiene salida SMTP; en
# DigitalOcean no la tiene. Se deja por si algun dia se migra de hosting.
ALERTA_EMAIL = os.environ.get("ALERTA_EMAIL", "").strip()
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
# Minimo de minutos entre alertas. Si el token muere y fallan 50 correos
# seguidos, no queremos 50 correos de alerta.
ALERTA_MINUTOS = int(os.environ.get("ALERTA_MINUTOS", "30"))

# Claves internas por asesor. Al agregar una nueva, verificar que no sea
# prefijo ni sufijo de otra: RML ya vive dentro de JRML.
CLAVES = {
    "AFR", "NVOT", "KTA", "HEVL", "GAC", "RML", "JRML",
    "CRA", "IJVP", "BBC", "AML", "NLP", "HSJ",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("captador")

# uid -> intentos fallidos. En memoria: si el proceso reinicia, se reintenta
# desde cero, que es exactamente lo que queremos.
intentos = {}


# --------------------------------------------------------------------------
# Lectura del correo
# --------------------------------------------------------------------------

def decodificar(valor):
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return str(valor)


def html_a_texto(html):
    """Aplana el HTML conservando los href: el enlace 'Ver aviso' puede traer
    el titulo completo del inmueble cuando el asunto lo trunca."""
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(
        r'(?is)<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>',
        r"\2 [\1]",
        html,
    )
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    for entidad, char in (
        ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
        ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
    ):
        html = html.replace(entidad, char)
    html = re.sub(r"[ \t]+", " ", html)
    return re.sub(r"\n{3,}", "\n\n", html).strip()


def extraer_texto(msg):
    """Prefiere text/plain; si no hay, aplana el HTML."""
    plano, html = None, None
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_maintype() == "multipart":
                continue
            if "attachment" in str(parte.get("Content-Disposition", "")):
                continue
            try:
                cuerpo = parte.get_payload(decode=True)
                if cuerpo is None:
                    continue
                cuerpo = cuerpo.decode(
                    parte.get_content_charset() or "utf-8", errors="replace"
                )
            except Exception:
                continue
            if parte.get_content_type() == "text/plain" and not plano:
                plano = cuerpo
            elif parte.get_content_type() == "text/html" and not html:
                html = cuerpo
    else:
        cuerpo = msg.get_payload(decode=True)
        if cuerpo:
            cuerpo = cuerpo.decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )
            if msg.get_content_type() == "text/html":
                html = cuerpo
            else:
                plano = cuerpo

    if plano and len(plano.strip()) > 200:
        return plano
    if html:
        return html_a_texto(html)
    return plano or ""


# --------------------------------------------------------------------------
# Extraccion con Claude
# --------------------------------------------------------------------------

if PROVEEDOR == "openai":
    from openai import OpenAI

    _cliente_ia = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
elif PROVEEDOR == "anthropic":
    from anthropic import Anthropic

    _cliente_ia = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
else:
    raise SystemExit(f"PROVEEDOR desconocido: {PROVEEDOR!r} (usa openai o anthropic)")

PROMPT = """Extraes datos de correos de portales inmobiliarios mexicanos \
reenviados a la bandeja de RE/MAX MID. Devuelves UNICAMENTE un objeto JSON \
valido, sin texto alrededor y sin bloques de codigo.

El remitente del correo es la inmobiliaria, NO el prospecto. Los datos del \
prospecto estan en el cuerpo, bajo "Datos del interesado" o "Datos de la \
persona interesada". Inmuebles24 enmascara el correo del prospecto en el \
remitente (@usuarios.inmuebles24.com): ese alias NO sirve, usa el que aparece \
en el campo "E-mail:" del cuerpo.

El correo puede traer un bloque "---------- Forwarded message ---------" \
(reenvio manual) o no traerlo (reenvio automatico). Ambos son validos.

Esquema:
{
  "es_lead": true,
  "codigo_propiedad": "string|null",
  "nombre": "string|null",
  "correo": "string|null",
  "telefono": "string|null",
  "clave_interna": "string|null",
  "portal": "string|null",
  "mensaje": "string|null",
  "confianza": "alta|media|baja"
}

Reglas:
- Si un dato no aparece, null. No inventes ni infieras.
- codigo_propiedad es el codigo del anunciante con formato EB-XXNNNN (aparece
  como "COD:EB-UW5094"). NO es el "Codigo de aviso" numerico.
- clave_interna: el texto entre las dos barras verticales del titulo del aviso
  ("Oficina Sobre Av Libano | Jrml |" -> "Jrml"). Si el titulo aparece cortado
  con "..." o no tiene barras, devuelve null. NO la deduzcas del nombre del
  asesor ni de ninguna otra parte del correo.
- telefono: si hay varios del mismo prospecto, devuelve el mas completo: el de
  12 digitos que empieza en 52 gana sobre el de 10.
- portal: el sitio que origino la consulta (Inmuebles24, Mercado Libre,
  EasyBroker, Propiedades.com...). Los correos que llegan desde
  @usuarios.vivanuncios.com.mx usan la plantilla de Inmuebles24: devuelve
  "Inmuebles24".
- mensaje: el texto que escribio el prospecto, si lo hay. Solo su mensaje, no
  el texto de plantilla del portal.
- es_lead: false si el correo no es la consulta de un prospecto por un inmueble
  (newsletters, facturacion, avisos del portal)."""


def extraer_datos(asunto, remitente, cuerpo):
    contenido = f"De: {remitente}\nAsunto: {asunto}\n\n{cuerpo[:20000]}"

    if PROVEEDOR == "openai":
        respuesta = _cliente_ia.chat.completions.create(
            model=MODELO,
            max_tokens=1000,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": contenido},
            ],
        )
        texto = respuesta.choices[0].message.content.strip()
    else:
        respuesta = _cliente_ia.messages.create(
            model=MODELO,
            max_tokens=1000,
            system=PROMPT,
            messages=[{"role": "user", "content": contenido}],
        )
        texto = respuesta.content[0].text.strip()

    # Por si el modelo devuelve el JSON envuelto en ``` pese a lo pedido.
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    return json.loads(texto)


# --------------------------------------------------------------------------
# Normalizacion
# --------------------------------------------------------------------------

def normalizar_telefono(valor):
    """A E.164. Sin esto GHL no marca ni manda WhatsApp."""
    if not valor:
        return None, False
    if valor.strip().startswith("+"):
        return "+" + re.sub(r"\D", "", valor), True
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) == 10:
        return "+52" + digitos, True
    if len(digitos) == 12 and digitos.startswith("52"):
        return "+" + digitos, True
    if len(digitos) == 11 and digitos.startswith("1"):
        return "+" + digitos, True
    return ("+" + digitos if digitos else None), False


def validar_clave(valor):
    """Comparacion exacta contra la lista, en mayusculas.

    Nunca por substring: RML esta contenido en JRML y cada lead de Juan
    Ricardo terminaria tambien en la cuenta de Rocio.
    """
    if not valor:
        return None
    token = re.sub(r"[^A-Za-z]", "", valor).upper()
    return token if token in CLAVES else None


# --------------------------------------------------------------------------
# GoHighLevel
# --------------------------------------------------------------------------

def crear_contacto(datos, telefono, clave, tel_ok):
    etiquetas = [ETIQUETA]
    if not clave:
        etiquetas.append("revisar-clave")
    if telefono and not tel_ok:
        etiquetas.append("revisar-telefono")

    # Los campos van por ID, no por "key". Probado contra la API: el formato
    # {"key": "contact.proyecto", ...} devuelve 201 y descarta el valor en
    # silencio; {"id": "<fieldId>", "field_value": ...} si lo guarda.
    campos = []
    if clave:
        campos.append({"id": CF_CLAVE_INTERNA, "field_value": clave})
    if datos.get("codigo_propiedad"):
        campos.append({"id": CF_PROYECTO, "field_value": datos["codigo_propiedad"]})

    # Partir el nombre. Si mandamos el nombre completo en firstName y el
    # contacto ya existe con apellido, GHL lo muestra duplicado
    # ("Leo Villalobosq Villalobosq").
    nombre = " ".join((datos.get("nombre") or "").split())
    partes = nombre.split(" ", 1)

    cuerpo = {
        "locationId": GHL_LOCATION_ID,
        "firstName": partes[0] if partes[0] else "",
        "tags": etiquetas,
        "customFields": campos,
    }
    # Solo si viene apellido. Mandarlo vacio borraria el que ya tenga
    # el contacto en GHL.
    if len(partes) > 1 and partes[1].strip():
        cuerpo["lastName"] = partes[1].strip()
    if datos.get("correo"):
        cuerpo["email"] = datos["correo"].strip().lower()
    if telefono:
        cuerpo["phone"] = telefono

    r = requests.post(
        f"{GHL_BASE}/contacts/upsert",
        headers=_headers(),
        json=cuerpo,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def crear_nota(contact_id, datos, telefono, clave, asunto):
    """Deja el contexto del correo en el contacto, para que el asesor vea de
    donde salio el lead sin tener que buscar el correo original."""
    lineas = [
        "📥 Lead recibido por LeadMaster (correo automatico)",
        f"Portal: {datos.get('portal') or '—'}",
        f"Mensaje: {datos.get('mensaje') or '—'}",
        f"Propiedad: {datos.get('codigo_propiedad') or '—'}",
        f"Telefono: {telefono or '—'}",
        f"Email: {datos.get('correo') or '—'}",
        f"Clave interna: {clave or '— (revisar)'}",
        f"Asunto del correo: {asunto}",
    ]
    r = requests.post(
        f"{GHL_BASE}/contacts/{contact_id}/notes",
        headers=_headers(),
        json={"body": "\n".join(lineas)},
        timeout=30,
    )
    r.raise_for_status()


def _headers():
    return {
        "Authorization": f"Bearer {GHL_TOKEN}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
    }


# --------------------------------------------------------------------------
# Procesamiento
# --------------------------------------------------------------------------

class FalloDefinitivo(Exception):
    """No tiene caso reintentar: el correo no sirve como lead."""


def procesar(crudo):
    msg = message_from_bytes(crudo)
    asunto = decodificar(msg.get("Subject"))
    remitente = decodificar(msg.get("From"))
    cuerpo = extraer_texto(msg)

    if not cuerpo.strip():
        raise FalloDefinitivo("correo sin cuerpo legible")

    datos = extraer_datos(asunto, remitente, cuerpo)

    if not datos.get("es_lead"):
        raise FalloDefinitivo("no es un lead de portal")

    telefono, tel_ok = normalizar_telefono(datos.get("telefono"))
    clave = validar_clave(datos.get("clave_interna"))

    # Sin datos de contacto no se crea nada. Nunca caer al remitente como
    # respaldo: el remitente es la inmobiliaria, no el prospecto.
    if not datos.get("correo") and not telefono:
        raise FalloDefinitivo("sin correo ni telefono del prospecto")

    respuesta = crear_contacto(datos, telefono, clave, tel_ok)
    contacto = respuesta.get("contact", {}) or {}

    # La nota es informativa: si falla, el lead ya esta en GHL y eso es lo que
    # importa. No tumbamos el procesamiento por esto.
    if contacto.get("id"):
        try:
            crear_nota(contacto["id"], datos, telefono, clave, asunto)
        except Exception as e:
            log.warning("contacto %s creado pero la nota fallo: %s",
                        contacto["id"], e)

    log.info(
        "OK  %s | %s | %s | %s | clave=%s | ghl=%s",
        datos.get("codigo_propiedad") or "-",
        (datos.get("nombre") or "-")[:25],
        datos.get("correo") or "-",
        telefono or "-",
        clave or "SIN CLAVE",
        contacto.get("id", "?"),
    )
    return True


_ultima_alerta = 0.0


def enviar_alerta(asunto, cuerpo):
    """Avisa por correo cuando un lead no pudo entrar a GHL.

    Nunca debe tumbar el procesamiento: si el aviso falla, se registra y ya.
    """
    global _ultima_alerta
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID) and not ALERTA_EMAIL:
        return
    ahora = time.time()
    if ahora - _ultima_alerta < ALERTA_MINUTOS * 60:
        return  # ya se aviso hace poco, no inundar

    enviada = False

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"⚠️ *{asunto}*\n\n{cuerpo}",
                    "parse_mode": "Markdown",
                },
                timeout=20,
            )
            r.raise_for_status()
            enviada = True
            log.info("alerta enviada por Telegram")
        except Exception as e:
            log.error("no se pudo enviar la alerta por Telegram: %s", e)

    # Correo solo si el hosting permite salida SMTP. En DigitalOcean no.
    if ALERTA_EMAIL and not enviada:
        try:
            msg = EmailMessage()
            msg["From"] = IMAP_USER
            msg["To"] = ALERTA_EMAIL
            msg["Subject"] = f"[captador] {asunto}"
            msg.set_content(cuerpo)
            with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=30) as s:
                s.login(IMAP_USER, IMAP_PASS)
                s.send_message(msg)
            enviada = True
            log.info("alerta enviada por correo a %s", ALERTA_EMAIL)
        except Exception as e:
            log.error("no se pudo enviar la alerta por correo: %s", e)

    if enviada:
        _ultima_alerta = ahora


def a_revisar(cliente, uid, motivo):
    log.warning("REVISAR uid=%s  %s", uid, motivo)
    try:
        if not cliente.folder_exists(CARPETA_REVISAR):
            cliente.create_folder(CARPETA_REVISAR)
        cliente.copy([uid], CARPETA_REVISAR)
    except Exception as e:
        log.error("no se pudo mover a %s: %s", CARPETA_REVISAR, e)
    cliente.add_flags([uid], [b"\\Seen"])
    intentos.pop(uid, None)


def procesar_pendientes(cliente):
    uids = cliente.search(["UNSEEN"])
    if not uids:
        return
    log.info("%d correo(s) por procesar", len(uids))

    for uid in uids:
        try:
            datos = cliente.fetch([uid], ["RFC822"])
            crudo = datos[uid][b"RFC822"]
        except Exception as e:
            log.error("uid=%s no se pudo descargar: %s", uid, e)
            continue

        try:
            procesar(crudo)
            cliente.add_flags([uid], [b"\\Seen"])
            intentos.pop(uid, None)
        except FalloDefinitivo as e:
            # No es un lead. Es lo normal con newsletters y avisos del portal,
            # asi que no se alerta.
            a_revisar(cliente, uid, str(e))
        except Exception as e:
            # Fallo posiblemente temporal (red, 5xx, limite de tasa).
            # Se deja sin leer para reintentar en la proxima vuelta.
            n = intentos.get(uid, 0) + 1
            intentos[uid] = n
            log.error("uid=%s intento %d/%d fallo: %s", uid, n, MAX_INTENTOS, e)

            # Un 401/403 no se arregla reintentando: el token murio o le
            # falta un permiso. Avisar de una vez, sin esperar los 3 intentos.
            texto = str(e)
            if "401" in texto or "403" in texto:
                enviar_alerta(
                    "el token de GoHighLevel dejo de funcionar",
                    "Los leads NO estan entrando a GHL.\n\n"
                    f"Error: {texto}\n\n"
                    "Que hacer:\n"
                    "1. Crear un token nuevo en GHL con los permisos\n"
                    "   contacts.readonly y contacts.write\n"
                    "2. En el servidor: cd /opt/captador && nano .env\n"
                    "3. Cambiar la linea GHL_TOKEN= por el nuevo\n"
                    "4. docker compose up -d\n\n"
                    "Los correos que fallaron quedan en la etiqueta REVISAR\n"
                    "del buzon. Para reprocesarlos: moverlos a Recibidos y\n"
                    "marcarlos como no leidos.",
                )

            if n >= MAX_INTENTOS:
                a_revisar(cliente, uid, f"agoto reintentos: {e}")
                enviar_alerta(
                    "un lead no pudo entrar a GHL",
                    f"Un correo agoto los {MAX_INTENTOS} intentos y se movio a "
                    f"la etiqueta {CARPETA_REVISAR}.\n\n"
                    f"Error: {texto}\n\n"
                    "El lead no se perdio: esta en esa etiqueta del buzon.",
                )


# --------------------------------------------------------------------------
# Bucle principal
# --------------------------------------------------------------------------

seguir = True


def detener(signum, frame):
    global seguir
    log.info("senal %s recibida, cerrando", signum)
    seguir = False


def main():
    signal.signal(signal.SIGTERM, detener)
    signal.signal(signal.SIGINT, detener)

    log.info("captador iniciado | buzon=%s | modelo=%s", IMAP_USER, MODELO)

    while seguir:
        try:
            with IMAPClient(IMAP_HOST, ssl=True) as cliente:
                cliente.login(IMAP_USER, IMAP_PASS)
                cliente.select_folder("INBOX")
                log.info("conectado, esperando correo")

                procesar_pendientes(cliente)

                while seguir:
                    cliente.idle()
                    # Timeout corto: Gmail corta el IDLE a los ~29 minutos y
                    # asi tambien detectamos si el proceso debe terminar.
                    respuestas = cliente.idle_check(timeout=300)
                    cliente.idle_done()
                    if respuestas:
                        procesar_pendientes(cliente)
                    else:
                        cliente.noop()  # mantiene viva la sesion
        except Exception as e:
            if not seguir:
                break
            log.error("conexion caida (%s), reintentando en 30s", e)
            time.sleep(30)

    log.info("captador detenido")


if __name__ == "__main__":
    main()
