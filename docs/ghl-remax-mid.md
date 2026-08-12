# Configuración GHL — RE/MAX MID

Sub-cuenta: `rkLMMyinmQJt6JTrZ8vE`
Token: guardado en credenciales de n8n (**no** en archivos ni en chat).

Validado con lecturas contra la API el 12/08/2026: el token responde 200 y tiene
lectura de pipelines y campos personalizados.

---

## Pipeline destino propuesto

**LEDS GENERAL** → `4NKQjki9fGiHlfIQKu7n`
**Etapa: Nuevo lead** → `f2ea9a68-6fc4-4400-838f-16ba8d04ce1e`

Alternativa a decidir con la clienta: los leads de tipo *"Consultaron tu
WhatsApp"* son más calientes (el prospecto ya intentó contacto directo) y podrían
entrar al pipeline **Milka IA Remax MID** (`ZG1a8GTYQWL53cXT3xg4`), etapa
**🤖 Milka On** (`5313ed92-dadf-4c94-adea-aa1a023df60e`) para que la IA los tome
de una vez, en lugar de esperar asignación manual.

Otros pipelines existentes: Alianzas, Listing de Propiedades, Reclutamiento de
Asesores, Rentas, Rhevo AI, Pipeline de prospectos.

---

## Campos personalizados que YA existen y hay que reusar

No crear duplicados. Estos ya están en la sub-cuenta:

| Campo GHL | fieldKey | Tipo | Qué se le manda |
|---|---|---|---|
| Canal de Venta | `contact.canal_de_venta` | SINGLE_OPTIONS | el portal |
| Presupuesto | `contact.presupuesto` | MONETORY | tope del rango que busca |
| Zona de interés y tiempo de entrega | `contact.zona_de_inters_y_tiempo_de_entrega` | TEXT | zonas que le interesan |
| Tipo de propiedad | `contact.tipo_de_propiedad` | TEXT | Casa / Departamento / Terreno / Oficina |
| Clave interna | `contact.clave_interna` | TEXT | código del anunciante (EB-XXXX) |
| Características específicas | `contact.caractersticas_especficas` | LARGE_TEXT | mensaje textual del prospecto |
| Fecha de primera interacción | `contact.fecha_de_primera_interaccin` | DATE | fecha del correo **original**, no la del reenvío |

### Golpe de suerte: `Canal de Venta` ya trae las opciones exactas

```
RE/MAX · Inmuebles24 · EasyBroker · Mercado Libre ·
The Smart Flat · Hey Hom · Properstar · Propiedades.com
```

Es un `SINGLE_OPTIONS`: **el valor tiene que coincidir exacto** con uno de esos,
o GHL lo descarta en silencio. La IA debe elegir de esa lista cerrada, nunca
inventar el nombre del portal.

### `Origen del Lead` no sirve tal cual

Solo tiene `LANDING` y `FORM FB`. Hay que agregarle la opción **`PORTAL`** a mano
en GHL antes de usarlo, o dejarlo vacío y apoyarse solo en `Canal de Venta`.

## No hay que crear ningún campo (verificado 12/08/2026)

Los dos que usa el captador ya existen:

| Dato | Campo GHL | fieldKey |
|---|---|---|
| Clave del asesor (`JRML`) | Clave interna | `contact.clave_interna` |
| Código de la propiedad (`EB-UW5094`) | Proyecto | `contact.proyecto` |

`Proyecto` es donde **AutoKPI ya escribe el código EB**, así que el captador
escribe ahí también y el dato no queda duplicado en dos campos distintos.

---

## Oportunidad

```
pipelineId:  4NKQjki9fGiHlfIQKu7n        (LEDS GENERAL)
stageId:     f2ea9a68-6fc4-4400-838f-16ba8d04ce1e   (Nuevo lead)
name:        <título del inmueble>
monetaryValue: <precio del aviso>
status:      open
```

Un contacto, varias oportunidades: si el mismo prospecto consulta tres inmuebles,
el contacto se actualiza y se abren tres oportunidades.

## Tags sugeridos

`portal-inmuebles24`, `portal-mercadolibre`, `lead-automatico`,
`consulta-whatsapp` / `consulta-mensaje`
