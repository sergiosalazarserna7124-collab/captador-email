"""
Reporte de correos recibidos en el buzon de captura, agrupado por asesor.

Responde: que llego, de que portal, y con la clave de quien. NO usa IA
—todo sale por expresiones regulares—, asi que no cuesta tokens y se puede
correr las veces que haga falta.

    python reporte.py [dias]      # por defecto 8

Lee el buzon COMPLETO (leidos y sin leer) y no toca ninguna bandera: es solo
lectura, no interfiere con el captador corriendo.
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

PORTALES = {
    "usuarios.inmuebles24.com": "Inmuebles24",
    "usuarios.vivanuncios.com.mx": "Vivanuncios",
    "inbox.easybroker.com": "EasyBroker",
    "mercadolibre.com": "Mercado Libre",
    "remax.com.mx": "RE/MAX",
}


def d(valor):
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return str(valor)


def texto_plano(msg):
    """Solo lo necesario para encontrar la clave: no hace falta el cuerpo entero."""
    partes = []
    for parte in msg.walk() if msg.is_multipart() else [msg]:
        if parte.get_content_type() not in ("text/plain", "text/html"):
            continue
        try:
            cuerpo = parte.get_payload(decode=True)
            if cuerpo:
                partes.append(cuerpo.decode(
                    parte.get_content_charset() or "utf-8", errors="replace"))
        except Exception:
            continue
    return " ".join(partes)[:8000]


def main():
    desde = datetime.now() - timedelta(days=DIAS)
    print(f"Buzon   : {IMAP_USER}")
    print(f"Periodo : ultimos {DIAS} dias (desde {desde:%Y-%m-%d})")
    print()

    por_clave = Counter()
    por_portal = Counter()
    sin_clave = []
    detalle = defaultdict(list)
    total = 0

    with IMAPClient(IMAP_HOST, ssl=True) as cli:
        cli.login(IMAP_USER, IMAP_PASS)
        cli.select_folder("INBOX", readonly=True)   # readonly: no marca nada
        uids = cli.search(["SINCE", desde.date()])

        for uid, datos in cli.fetch(uids, ["RFC822"]).items():
            crudo = datos.get(b"RFC822")
            if not crudo:
                continue
            msg = message_from_bytes(crudo)
            asunto = d(msg.get("Subject"))
            frm = d(msg.get("From"))
            todo = asunto + " " + texto_plano(msg)

            dom = RE_DOM.search(frm)
            dom = dom.group(1).lower().rstrip(">") if dom else "?"
            portal = next((v for k, v in PORTALES.items()
                           if dom == k or dom.endswith("." + k)), None)
            if not portal:
                continue          # no es de un portal: fuera del reporte

            total += 1
            por_portal[portal] += 1

            eb = RE_EB.search(todo)
            eb = eb.group(0) if eb else "-"
            try:
                fecha = parsedate_to_datetime(msg.get("Date")).strftime("%m-%d %H:%M")
            except Exception:
                fecha = "?"

            claves = {c.upper() for c in RE_CLAVE.findall(todo) if 2 <= len(c) <= 6}
            if claves:
                for c in claves:
                    por_clave[c] += 1
                    detalle[c].append(f"{fecha}  {eb:<11} {portal}")
            else:
                sin_clave.append(f"{fecha}  {eb:<11} {portal:<14} {asunto[:44]}")

    print("=" * 66)
    print(f"LEADS POR ASESOR   (total de correos de portales: {total})")
    print("=" * 66)
    if por_clave:
        for clave, n in por_clave.most_common():
            print(f"  {clave:<8} {n:>3} lead(s)")
    else:
        print("  (ninguno con clave legible)")

    print()
    print(f"  SIN CLAVE {len(sin_clave):>3}  (titulo truncado o aviso sin clave)")

    print()
    print("=" * 66)
    print("POR PORTAL")
    print("=" * 66)
    for portal, n in por_portal.most_common():
        print(f"  {portal:<16} {n:>3}")

    print()
    print("=" * 66)
    print("DETALLE POR ASESOR")
    print("=" * 66)
    for clave in sorted(detalle):
        print(f"\n  {clave}  ({len(detalle[clave])})")
        for linea in sorted(detalle[clave]):
            print(f"     {linea}")

    if sin_clave:
        print()
        print("=" * 66)
        print("SIN CLAVE ASIGNABLE")
        print("=" * 66)
        for linea in sorted(sin_clave):
            print(f"  {linea}")


if __name__ == "__main__":
    main()
