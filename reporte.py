"""
Reporte de leads recibidos, agrupado por clave de asesor.

Por cada lead: fecha, codigo de propiedad, portal, y los datos de quien
pregunto (nombre, correo, telefono).

    python reporte.py [dias]      # por defecto 8

NO usa IA: todo sale por expresiones regulares, asi que no cuesta tokens.
Lee el buzon en modo solo-lectura: no marca nada y no interfiere con el
captador corriendo.
"""

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from imapclient import IMAPClient

DIAS = int(sys.argv[1]) if len(sys.argv) > 1 else 8

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ["IMAP_USER"]
IMAP_PASS = os.environ["IMAP_PASS"]

RE_EB = re.compile(r"EB-[A-Z]{2}\d{4}")
RE_CLAVE = re.compile(r"\|\s*([A-Za-z]{2,6})\s*\|")
RE_DOM = re.compile(r"@([\w.-]+)")
RE_MAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")

PORTALES = {
    "usuarios.inmuebles24.com": "Inmuebles24",
    "usuarios.vivanuncios.com.mx": "Vivanuncios",
    "inbox.easybroker.com": "EasyBroker",
    "mercadolibre.com": "Mercado Libre",
    "remax.com.mx": "RE/MAX",
}

# Correos que son del portal o de la propia inmobiliaria: nunca son el prospecto.
DOMINIOS_NO_PROSPECTO = (
    "inmuebles24.com", "vivanuncios.com.mx", "easybroker.com", "mercadolibre.com",
    "remax.com.mx", "remax-mid.com.mx", "mercadolibre.com.mx", "1e100.net",
    "sendgrid.net", "google.com", "gmail.com.mx",
)

# El nombre viene con etiqueta distinta segun el portal.
RE_NOMBRE = [
    re.compile(r"Nombre y apellido\s*:\s*(.{2,60}?)\s*(?:\n|Tel|E-?mail|$)", re.I),
    re.compile(r"===\s*Enviado por\s*:\s*===\s*\n\s*(.{2,60}?)\s*\n", re.I),
    re.compile(r"Enviado por\s*:?\s*\n\s*(.{2,60}?)\s*\n", re.I),
    re.compile(r"Nombre\s*:\s*(.{2,60}?)\s*(?:\n|Email|Tel|$)", re.I),
    re.compile(r"^\s*(.{3,60}?)\s+te pregunt", re.I | re.M),
]


def d(valor):
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return str(valor)


def html_a_texto(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</td>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                    ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        html = html.replace(ent, ch)
    html = re.sub(r"[ \t]+", " ", html)
    return re.sub(r"\n{3,}", "\n\n", html)


def cuerpo_texto(msg):
    plano, html = None, None
    for parte in (msg.walk() if msg.is_multipart() else [msg]):
        tipo = parte.get_content_type()
        if tipo not in ("text/plain", "text/html"):
            continue
        try:
            raw = parte.get_payload(decode=True)
            if not raw:
                continue
            txt = raw.decode(parte.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if tipo == "text/plain" and not plano:
            plano = txt
        elif tipo == "text/html" and not html:
            html = txt
    if plano and len(plano.strip()) > 200:
        return plano
    return html_a_texto(html) if html else (plano or "")


def datos_prospecto(texto):
    """Nombre, correo y telefono de quien pregunto."""
    nombre = None

    # EasyBroker: el nombre es la primera linea util despues de "Enviado por".
    # Va por lineas y no por regex porque en medio hay lineas en blanco.
    lineas_txt = [l.strip() for l in texto.splitlines()]
    for i, linea in enumerate(lineas_txt):
        if "enviado por" not in linea.lower():
            continue
        for siguiente in lineas_txt[i + 1:i + 6]:
            # quitar los <https://...> y <mailto:...> que EasyBroker pega
            # al lado del nombre: traen digitos y confundian el filtro.
            cand = re.sub(r"<[^>]*>", " ", siguiente).strip(" :=-")
            if (len(cand) >= 3 and not RE_MAIL.search(cand)
                    and not re.search(r"\d{6}", cand)
                    and not cand.lower().startswith(("responder", "http"))):
                nombre = re.sub(r"\s+", " ", cand)[:40]
                break
        if nombre:
            break

    if not nombre:
        for patron in RE_NOMBRE:
            m = patron.search(texto)
            if m:
                cand = re.sub(r"\s+", " ", m.group(1)).strip(" :- ")
                if cand and not RE_MAIL.search(cand) and not cand.isdigit():
                    nombre = cand[:40]
                    break

    correo = None
    for c in RE_MAIL.findall(texto):
        cl = c.lower()
        if not any(cl.endswith("@" + dm) or cl.endswith("." + dm)
                   for dm in DOMINIOS_NO_PROSPECTO):
            correo = cl
            break

    # Preferir el de 12-13 digitos (trae lada de pais) sobre el de 10.
    digitos = [re.sub(r"\D", "", t) for t in re.findall(r"\+?\d[\d\s().-]{8,16}", texto)]
    digitos = [x for x in digitos if 10 <= len(x) <= 13]
    telefono = None
    if digitos:
        largos = [x for x in digitos if len(x) >= 12]
        telefono = (largos or digitos)[0]

    return nombre, correo, telefono


def main():
    desde = datetime.now() - timedelta(days=DIAS)
    print(f"Buzon   : {IMAP_USER}")
    print(f"Periodo : ultimos {DIAS} dias (desde {desde:%Y-%m-%d})\n")

    por_clave = Counter()
    por_portal = Counter()
    detalle = defaultdict(list)
    sin_clave = []
    total = 0

    with IMAPClient(IMAP_HOST, ssl=True) as cli:
        cli.login(IMAP_USER, IMAP_PASS)
        cli.select_folder("INBOX", readonly=True)
        uids = cli.search(["SINCE", desde.date()])

        for uid, datos in cli.fetch(uids, ["RFC822"]).items():
            crudo = datos.get(b"RFC822")
            if not crudo:
                continue
            msg = message_from_bytes(crudo)
            asunto = d(msg.get("Subject"))
            frm = d(msg.get("From"))

            m = RE_DOM.search(frm)
            dom = m.group(1).lower().rstrip(">") if m else "?"
            portal = next((v for k, v in PORTALES.items()
                           if dom == k or dom.endswith("." + k)), None)
            if not portal:
                continue

            total += 1
            por_portal[portal] += 1

            texto = cuerpo_texto(msg)
            todo = asunto + "\n" + texto
            eb = RE_EB.search(todo)
            eb = eb.group(0) if eb else "-"
            try:
                fecha = parsedate_to_datetime(msg.get("Date")).strftime("%m-%d %H:%M")
            except Exception:
                fecha = "?"

            nombre, correo, telefono = datos_prospecto(texto)
            fila = (f"{fecha}  {eb:<11} {portal:<14} "
                    f"{(nombre or '-')[:28]:<28} {(correo or '-')[:34]:<34} "
                    f"{telefono or '-'}")

            claves = {c.upper() for c in RE_CLAVE.findall(todo) if 2 <= len(c) <= 6}
            if claves:
                for c in claves:
                    por_clave[c] += 1
                    detalle[c].append(fila)
            else:
                sin_clave.append(fila)

    con = sum(por_clave.values())
    print("=" * 118)
    print(f"RESUMEN   correos de portales: {total}   con clave: {con}   sin clave: {len(sin_clave)}")
    print("=" * 118)
    for clave, n in por_clave.most_common():
        print(f"  {clave:<8} {n:>3}")
    print(f"\n  {'SIN CLAVE':<8} {len(sin_clave):>3}")

    print("\n" + "=" * 118)
    print("POR PORTAL")
    print("=" * 118)
    for portal, n in por_portal.most_common():
        print(f"  {portal:<16} {n:>3}")

    cab = (f"{'FECHA':<14} {'PROPIEDAD':<11} {'PORTAL':<14} "
           f"{'NOMBRE':<28} {'CORREO':<34} TELEFONO")

    print("\n" + "=" * 118)
    print("LEADS CON CLAVE INTERNA")
    print("=" * 118)
    for clave in sorted(detalle):
        print(f"\n  ── {clave}  ({len(detalle[clave])}) " + "─" * 60)
        print("  " + cab)
        for linea in sorted(detalle[clave]):
            print("  " + linea)

    print("\n" + "=" * 118)
    print(f"LEADS SIN CLAVE INTERNA  ({len(sin_clave)})")
    print("=" * 118)
    print("  " + cab)
    for linea in sorted(sin_clave):
        print("  " + linea)


if __name__ == "__main__":
    main()
