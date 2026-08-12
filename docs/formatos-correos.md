# Formatos de correo detectados

Analizados 5 correos reales de RE/MAX MID (`contacto@remax-mid.com.mx`),
11–12 de agosto 2026. **No son 5 formatos: son 2.**

---

## Formato A — Inmuebles24 (4 de 5)

Remitente original: `<nombre> mediante Inmuebles24 <alias@usuarios.inmuebles24.com>`

Ojo: uno de los cuatro llegó desde `@usuarios.vivanuncios.com.mx`. **Misma
plantilla, mismo grupo.** No lo trates como portal aparte, salvo que la clienta
quiera distinguirlo en el reporte.

Tres asuntos distintos, misma estructura:

- `📱 ¡Consultaron tu WhatsApp en el aviso X! CÓD:EB-XXXX - REF:#XXXXXX#`
- `📩 ¡Recibiste una nueva consulta por el aviso X! CÓD:EB-XXXX - REF:#XXXXXX#`

Cuerpo:

```
¡Hola, REMAX/MID!
Hay interesados que consultaron tu número de WhatsApp por el siguiente aviso:
MN 13,000 No especificado
Fraccionamiento Gran Santa Fe,…
 1 m2
  3 recámaras   2 baños   1 estacionamiento
Renta  |  Casa       Ver aviso
Código de aviso: 149986363   Código del anunciante: EB-QY2819

Datos del interesado
Nombre y apellido: FERNANDO
Teléfono: 9992977467
Teléfono: 529992977467
 E-mail: promcapi@hotmail.com

Conoce lo que busca FERNANDO en un inmueble
Tu contacto busca:
 Casa en Alquiler
  MXN 12.000 - MXN 38.000
Le interesa encontrar un inmueble en:
Fraccionamiento Gran Santa Fe  Temozón Norte  Santa Gertrudis  Copo  Benito Juárez Nte

La respuesta de este email será enviada a promcapi@hotmail.com
```

## Formato B — Mercado Libre (1 de 5)

Remitente original: `Mercado Libre <no-responder@mercadolibre.com>`
Asunto: `Te contactaron en <título> #2945639643`

```
Maria Georgina Guadalupe Caamal Sosa te preguntó:
Hola Remax Mid, Estoy interesado en Casa Dentro De Mérida Muy Cerca De
Periférico, por favor comunícate conmigo. ¡Gracias!

Datos de la persona interesada
 Maria Georgina Guadalupe Caamal Sosa AUTOS PONIENTE
 autosponiente@hotmail.com
 9993445782
```

Trae **menos** datos: sin precio, sin código de anunciante, sin perfil de
búsqueda. Solo el ID del aviso en el asunto. A cambio, el **nombre completo real**
(Inmuebles24 suele dar solo el alias: "FERNANDO", "dixie").

---

## Las 6 trampas de estos correos

### 1. El correo del prospecto NO es el del remitente

Inmuebles24 manda desde un alias enmascarado:

```
De:  lic.dixiechi@usuarios.inmuebles24.com     ← alias, NO sirve
Body: E-mail: lic.dixiechi@hotmail.com          ← el real
"La respuesta de este email será enviada a lic.dixiechi@hotmail.com"  ← confirma
```

Siempre el del cuerpo. Nunca el del `From`.

### 2. Llegan dos teléfonos, son el mismo

```
Teléfono: 9992977467
Teléfono: 529992977467
```

Regla: si hay uno de 12 dígitos que empieza en `52`, ese gana → `+529992977467`.
Si solo viene el de 10 → anteponer `+52`. Nunca crear dos contactos.

### 3. Los separadores de miles cambian dentro del MISMO correo

```
MN 13,000                       ← precio del aviso, coma
MXN 12.000 - MXN 38.000         ← presupuesto del prospecto, punto
```

`MXN 12.000` son **doce mil**, no doce. Si el parser lo lee como decimal, el
campo Presupuesto de GHL queda en $12 y el perfilamiento se vuelve basura.

### 4. Hay campos con valores basura

`1 m2` en una casa de 3 recámaras (Formato A, ejemplo 1). El portal permite
publicar sin superficie. Si `metros <= 5`, mandar vacío en vez del número.

### 5. Dos niveles de intención en el mismo formato

`Consultaron tu WhatsApp` = el prospecto **ya intentó** contacto directo.
`Recibiste una nueva consulta` / `Te contactaron` = solo dejó mensaje.

El primero es notablemente más caliente. Vale la pena separarlos, no meterlos
todos al mismo cajón.

### 6. El reenvío automático no se ve igual que el manual

Los 5 ejemplos fueron reenviados **a mano**, y Gmail les insertó el bloque:

```
---------- Forwarded message ---------
De: ... / Date: ... / Subject: ... / To: ...
```

El reenvío **automático** (filtro → reenviar a) normalmente **no** inserta ese
bloque: reenvía el mensaje conservando las cabeceras originales. Son dos formas
distintas de ver lo mismo.

Consecuencia práctica: el prompt debe funcionar con y sin ese bloque, y **hay
que probar con un reenvío automático real antes de salir a producción**. Es el
punto donde más fácil se rompe todo sin que nadie se entere.

---

## El dato que nadie está aprovechando

Inmuebles24 ya te está regalando el perfilamiento:

```
Tu contacto busca: Casa en Alquiler
MXN 12.000 - MXN 38.000
Le interesa encontrar un inmueble en:
Fraccionamiento Gran Santa Fe, Temozón Norte, Santa Gertrudis, Copo, Benito Juárez Nte
```

Presupuesto y zonas de interés, en el correo, gratis. Eso es exactamente lo que
Milka IA tendría que sacar preguntando por WhatsApp. Mapeado a los campos
`Presupuesto` y `Zona de interés y tiempo de entrega` que ya existen, el asesor
abre el contacto y ya sabe qué ofrecerle.

Solo lo trae el Formato A. Mercado Libre no.
