# Captador de leads — Gmail → Claude → GoHighLevel

Un solo proceso. Sin base de datos, sin interfaz, sin proxy inverso.

```
Portales → contacto@remax-mid.com.mx → reenvío → Gmail de captura
                                                      ↓  IMAP IDLE
                                                  captador
                                                      ↓
                                          Claude extrae 5 campos
                                                      ↓
                                          GHL /contacts/upsert
```

**~50 MB de RAM.** Cabe de sobra en el droplet junto a Evolution API.

## El estado vive en IMAP

No hay base de datos porque no hace falta:

| Situación | Qué pasa con el correo |
|---|---|
| Procesado correctamente | se marca como **leído** |
| Fallo temporal (red, 5xx) | **sigue sin leer** → se reintenta solo |
| 3 intentos fallidos | copia a la etiqueta **REVISAR** + leído |
| No es un lead | a **REVISAR** directo, sin reintentar |

Si el proceso se cae, los correos se acumulan sin leer en Gmail y al volver los
procesa todos. **No se pierde ningún lead.** Y si algo sale mal, queda un correo
sin leer o una etiqueta REVISAR con contenido: los fallos son visibles.

---

## Instalación

```bash
cd /opt && git clone <repo> captador && cd captador/procesador
cp .env.example .env    # rellenar
docker compose up -d --build
docker compose logs -f
```

## Antes de arrancar

1. **Gmail de captura**: cuenta creada, verificación en 2 pasos activada y
   **contraseña de aplicación** generada (la normal no sirve para IMAP).
2. **Campo en GHL**: crear `Código de propiedad` (tipo TEXT). Si el `key` no
   existe, GHL responde 200 y descarta el valor en silencio.
3. **Reenvío**: desde `contacto@remax-mid.com.mx` hacia el buzón de captura.
   Gmail manda un código de confirmación que hay que abrir y aprobar.

## Verificar que funciona

```bash
docker compose logs -f captador
```

Una línea por lead:

```
OK  EB-UW5094 | Leo Villalobosq | leovillalobos1812@gmail.com | +529992191094 | clave=JRML | ghl=abc123
```

`clave=SIN CLAVE` significa que el asunto venía truncado: el contacto se creó
igual, con la etiqueta `revisar-clave` en GHL.

## Operación diaria

```bash
docker compose logs --since 24h | grep -c "^.*OK "        # leads del día
docker compose logs --since 24h | grep -E "ERROR|REVISAR" # lo que falló
```

Y en Gmail, la etiqueta **REVISAR**: si está vacía, todo va bien.

## Cambios frecuentes

- **Agregar una clave de asesor** → `CLAVES` en `main.py`. Verificar que la nueva
  no sea prefijo ni sufijo de otra (`RML` ya vive dentro de `JRML`).
- **Ajustar la extracción** → constante `PROMPT` en `main.py`.
- **Rotar el token de GHL** → `.env` y `docker compose up -d`.

Después de cualquier cambio: `docker compose up -d --build`.

## Costo

~US$0,003 por correo (Claude Haiku). Unos **US$3 por cada 1.000 leads**.
El droplet ya está pagado.

---

## Cuándo esto se queda corto

Este script hace una cosa y la hace bien. Convendría pasar a n8n si algún día:

- se suman varias inmobiliarias con reglas distintas cada una,
- alguien sin perfil técnico necesita ajustar el flujo,
- el flujo deja de ser lineal (ramas, esperas, aprobaciones).

Mientras sea *un correo entra, un contacto sale*, el script gana por todos lados.
