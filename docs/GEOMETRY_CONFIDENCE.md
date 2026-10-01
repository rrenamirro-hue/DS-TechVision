# Confianza geométrica y separación de datos

## Estados permitidos

| Estado | Interpretación | Uso actual |
| --- | --- | --- |
| `OEM_MEASURED` | Medida explícita del documento OEM | Dimensiones externas de variantes con y sin NFC |
| `OEM_DIAGRAM_DERIVED` | Relación obtenida de un dibujo OEM sin escala métrica | Reservado para futuras revisiones documentadas |
| `OEM_IMAGE_APPROXIMATED` | Proporción estimada visualmente de foto o diagrama | Tamaño y posición de las mallas internas |
| `SIMULATION_ONLY` | Animación o estado conceptual del visor | Estados, separación y movimientos |
| `PHYSICAL_VALIDATION_REQUIRED` | Corrección local aún sin contrastar con la máquina | Correcciones y anchors pendientes |
| `PHYSICALLY_VALIDATED` | Contrastado con equipo real | Prohibido en 0.4: no hay impresora física |

`APPROXIMATED_FROM_OEM_IMAGE` del planteo se representa en los datos como `OEM_IMAGE_APPROXIMATED`, el valor normalizado del sistema de confianza. Cada geometría interna tiene `estimated: true`, `measurement_source` y `geometry_status`. La envolvente global usa `estimated: false` con página OEM precisa. Las trayectorias tienen `distance_status: APPROXIMATED`; sus 90 mm son un parámetro visual de animación, no una distancia de desmontaje.

## Reglas de trazabilidad

1. La medida externa se toma del Service Manual Rev. 6, página impresa 10 / PDF 21.
2. Los part numbers y cantidades del conjunto Reader/ADF se toman de Parts Catalog Rev. 9, figura 160, páginas PDF 44-45.
3. Cubiertas, cassette, motor y panel conservan la figura específica del catálogo.
4. El orden y las acciones del desmontaje provienen del procedimiento OEM ya estructurado en `data/procedures/adf_reader.json`, Service Manual PDF 151-152.
5. Las páginas de preparación provienen del mismo Service Manual. La imagen mostrada es una representación extraída del PDF original.
6. Los grupos sin part number son nodos topológicos o representaciones visuales; no se etiquetan como piezas OEM individuales.

## Corrección futura

La clave persistente es `(usuario, model_id, component_id, state_id)`. El registro admite `scale`, `offset_mm[3]`, `rotation_deg[3]` y `anchor_offset[2]`. El offset del anchor se expresa como fracción del ancho del QR. La API valida modelo, componente y estado conocidos. Las correcciones no alteran `equipment_dimensions.json`, el inventario ni los PDF. Sólo se podrán marcar físicamente validadas tras medir un equipo real y documentar la evidencia.
