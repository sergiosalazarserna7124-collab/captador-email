# Chuleta — captador de leads

## Dónde está todo

| Qué | Dónde |
|---|---|
| Código en tu Mac (aquí se edita) | `/Users/sergio/Desktop/nuri projet/procesador/` |
| Código en el servidor (aquí corre) | `/opt/captador/` |
| Credenciales | `/opt/captador/.env` — **solo en el servidor** |
| Servidor | `147.182.209.15` (DigitalOcean, `evolution-leadmaster`) |
| Buzón de captura | `capturasremaxmid@gmail.com` |
| Sub-cuenta GHL | `rkLMMyinmQJt6JTrZ8vE` (RE/MAX MID) |

## Entrar al servidor

```bash
ssh root@147.182.209.15
```

```bash
cd /opt/captador
```

---

## Logs

**Ver en vivo** (queda enganchado, salir con `control + C`):

```bash
docker compose logs -f
```

**Últimas 30 líneas** y te devuelve el control:

```bash
docker compose logs --tail 30
```

**Los leads de las últimas 24 horas:**

```bash
docker compose logs --since 24h | grep " OK "
```

**Cuántos leads entraron hoy:**

```bash
docker compose logs --since 24h | grep -c " OK "
```

**Lo que falló:**

```bash
docker compose logs --since 24h | grep -E "ERROR|WARNING"
```

**Los que quedaron sin clave interna** (última semana):

```bash
docker compose logs --since 168h | grep "SIN CLAVE"
```

> `--since` solo entiende horas, minutos y segundos: `24h`, `168h`, `30m`.
> `7d` da error.

### Cómo se lee una línea de log

```
OK  EB-UW5094 | Leo Villalobosq | correo@x.com | +52999... | clave=JRML | ghl=zJLpt...
    └código┘   └── nombre ──┘   └─ correo ─┘   └teléfono┘   └ asesor ┘   └id en GHL┘
```

`clave=SIN CLAVE` → el asunto venía truncado. El contacto se creó igual, con la
etiqueta `revisar-clave` en GHL.

---

## Operación

**Ver si está vivo:**

```bash
docker compose ps
```

**Reiniciar** (sin cambiar código):

```bash
docker compose restart
```

**Apagar:**

```bash
docker compose down
```

**Prender:**

```bash
docker compose up -d
```

**Cambiar credenciales:**

```bash
nano .env
```

Guardar con `control+O`, `Enter`, salir con `control+X`. Luego:

```bash
docker compose up -d
```

---

## Actualizar el código

Después de editar `main.py` en el Mac, cuatro pasos:

**1.** Salir del servidor:

```bash
exit
```

**2.** En el Mac, mandar el archivo:

```bash
scp "/Users/sergio/Desktop/nuri projet/procesador/main.py" root@147.182.209.15:/opt/captador/main.py
```

**3.** Volver a entrar:

```bash
ssh root@147.182.209.15
```

**4.** Reconstruir:

```bash
cd /opt/captador && docker compose up -d --build
```

---

## Cambios frecuentes en `main.py`

| Qué cambiar | Dónde, dentro del archivo |
|---|---|
| Agregar clave de asesor | constante `CLAVES` (arriba, ~línea 50) |
| Ajustar qué extrae la IA | constante `PROMPT` |
| Texto de la nota | función `crear_nota` |
| Regla del teléfono | función `normalizar_telefono` |

> Al agregar una clave nueva, verifica que **no sea prefijo ni sufijo de otra**.
> `RML` ya vive dentro de `JRML`, y por eso la comparación es exacta y no por
> "contiene".

---

## En qué terminal estoy

La única regla que importa:

| Dice | Estás en |
|---|---|
| `sergio@MacBook-Air-de-sergio` | tu Mac |
| `root@evolution-leadmaster` | el servidor |

`scp` se corre desde el **Mac**. `docker` desde el **servidor**.
