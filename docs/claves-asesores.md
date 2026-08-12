# Claves internas — RE/MAX MID

Fuente: `CLAVES INTERNAS ASESORES REMAX MID.pdf` (13 asesores).
Faltan ~5 por confirmar.

| Asesor | Clave |
|---|---|
| Alvaro Ivan Flores Rivera | `AFR` |
| Nydia Veronica Onofre Tolentino | `NVOT` |
| Katherine Tosquy Adriano | `KTA` |
| Hector Emilio Vera Lopez | `HEVL` |
| Gabriela Armengol Cano | `GAC` |
| Rocio Moriel Lopez | `RML` |
| Juan Ricardo Martinez Lizarraga | `JRML` |
| Carolina Ramirez Alvarado | `CRA` |
| Ingrid Jacobson Varela Pindter | `IJVP` |
| Berenice Blanca Casarrubias | `BBC` |
| Alejandra Martinez de Lira | `AML` |
| Nuri Lizarraga Pahul | `NLP` |
| Hugo Sanchez Juarez | `HSJ` |

---

## ⚠️ `RML` está contenido dentro de `JRML`

**Rocio Moriel Lopez = `RML`** y **Juan Ricardo Martinez Lizarraga = `JRML`**.

Si el emparejamiento se hace con "contiene", cada lead de Juan Ricardo se le
asigna también a Rocío. Es el tipo de error que nadie nota durante semanas.

Reglas obligatorias:

1. **Extraer primero, comparar después.** Sacar el texto entre las dos barras del
   título con `\|\s*([A-Za-z]{2,6})\s*\|` y comparar ese token **completo**
   contra la lista. Nunca buscar la clave dentro del asunto con `includes`.
2. **Comparación exacta, sin distinguir mayúsculas.** En los correos aparece
   `Jrml`, en el PDF `JRML`. Normalizar ambos lados a mayúsculas.
3. **Si el token no está en la lista, dejar vacío** y etiquetar `revisar-clave`.
   Es una de las 5 que faltan, o un asesor nuevo. Nunca aproximar al más parecido.

Al agregar las 5 que faltan, revisar que ninguna nueva sea prefijo o sufijo de
otra existente.

---

## Dónde vive la clave

En el **título del aviso**, entre barras, antes del código:

```
Subject: 📱 ¡Consultaron tu WhatsApp en el aviso Oficina Sobre Av Líbano | Jrml |! CÓD:EB-UW5094 - REF:#491245768#
                                                                        └──┬──┘
                                                                     clave interna
```

### El asunto trunca los títulos largos

De los 5 correos analizados, la clave solo era legible en 1:

| Asunto | Resultado |
|---|---|
| `…Oficina Sobre Av Líbano \| Jrml \|! CÓD:EB-UW5094` | `JRML` |
| `…Departamento con Espectacular Vista! en Las Co **...**!` | truncado |
| `…Lotes en Venta Privada Residencial en San Igna **...**!` | truncado |
| `…Casa en Renta Amueblada!` | sin barras |
| Mercado Libre | no aplica |

Como la clave va al **final** del título, es lo primero que se pierde al cortar.

**Comportamiento cuando no se puede leer:** el contacto se crea igual, con los
otros 4 campos, la clave vacía y la etiqueta `revisar-clave`. No se adivina y no
se pierde el lead — queda visible en GHL para completar a mano.

Pendiente de verificar con un `.eml` crudo: si el enlace "Ver aviso" del cuerpo
conserva el título completo, se recuperan los truncados sin depender de nada más.
