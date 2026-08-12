# Seguridad del captador

## Qué está expuesto realmente

El captador **no abre ningún puerto**. Solo hace conexiones salientes (Gmail,
OpenAI, GHL). No hay forma de "entrarle" desde internet: no escucha nada.

La superficie de ataque del droplet es otra:

| Puerta | Riesgo | Estado |
|---|---|---|
| SSH (puerto 22) | fuerza bruta contra la contraseña de root | ⚠️ contraseña habilitada |
| Evolution API (puerto HTTP) | si está expuesto sin auth, es la puerta más grande | ⚠️ revisar |
| El captador | ninguno, no escucha | ✅ |

## Qué se pierde si alguien entra

El `.env` tiene tres llaves. Ordenadas por daño:

1. **Token de GHL** — acceso completo a la base de contactos de la clienta. Es lo
   más valioso que hay en ese servidor.
2. **Contraseña de aplicación de Gmail** — leer el buzón de captura.
3. **API key de OpenAI** — gastar tu saldo.

---

## Lo que hay que hacer, por orden de importancia

### 1. Rotar lo que pasó por el chat  🔴

El token de GHL, la contraseña de la cuenta de Gmail, la de aplicación y la del
servidor quedaron en el historial de una conversación. Ninguna es catastrófica
por sí sola, pero el token de GHL sí da acceso a toda la base de contactos.

- GHL → Settings → Private Integrations → revocar el token anterior y crear otro
- Google → revocar la contraseña de aplicación `captador` y generar otra
- Actualizar `/opt/captador/.env` y `docker compose up -d`

### 2. Apagar el acceso por contraseña en SSH  🔴

Tu llave ya está instalada, así que la contraseña solo sirve para que la
adivinen. Los bots escanean el puerto 22 todo el día.

Primero, mira qué hay configurado:

```bash
grep -rE "^\s*PasswordAuthentication" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null
```

Luego desactívalo donde corresponda y verifica **antes de cerrar la sesión**:

```bash
sshd -T | grep -i passwordauthentication
```

Debe decir `passwordauthentication no`.

> **Sin riesgo de quedarte afuera:** aunque algo salga mal, el botón
> **Web Console** de DigitalOcean entra siempre, sin llaves ni contraseña.
> Prueba abrir una segunda terminal con `ssh` antes de cerrar la que tienes.

### 3. Revisar qué expone Evolution API  🟠

```bash
ss -tlnp | grep -v 127.0.0.1
```

Eso lista lo que escucha hacia afuera. Si Evolution API está publicado sin
autenticación, es un problema mayor que cualquier cosa del captador. Mándame la
salida y lo revisamos.

### 4. Actualizaciones automáticas de seguridad  🟠

Hay 12 actualizaciones pendientes.

```bash
apt update && apt upgrade -y
```

```bash
apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades
```

> **No dejes que reinicie solo.** Un reinicio automático tumba la sesión de
> WhatsApp de Evolution API. En `/etc/apt/apt.conf.d/50unattended-upgrades`,
> `Unattended-Upgrade::Automatic-Reboot` debe quedar en `"false"`.

### 5. Firewall  🟡

```bash
ufw allow OpenSSH && ufw enable
```

Antes de activarlo, **agrega los puertos que Evolution API necesite** o lo dejas
sin servicio. Por eso va después del punto 3.

---

## Lo que ya está bien

- `.env` con permisos `600`: solo root lo lee
- `.gitignore` que impide subir credenciales a un repositorio
- El contenedor corre como usuario sin privilegios (`captador`), no como root
- Tope de memoria de 256 MB: el captador no puede ahogar a Evolution API
- Token de GHL con scopes mínimos (contactos y oportunidades, nada más)
- El captador no escucha ningún puerto

## Higiene continua

- Las credenciales van **directo del navegador al `.env`**, sin pasar por chat,
  correo ni WhatsApp
- Los 16 caracteres de Gmail son revocables sin tocar el resto de la cuenta: si
  algo se filtra, revocas esa y listo
- Si algún día vendes esto a otra inmobiliaria, **un token de GHL por cliente**.
  Nunca uno compartido entre sub-cuentas
