# DS TechVision 0.4 - gemelo digital aproximado

## Alcance y procedencia

La variante inicial es Canon imageRUNNER 1643i **sin NFC**. El Service Manual Rev. 6, página impresa 10 / PDF 21, indica 480 × 464 × 452 mm (ancho × profundidad × alto). Para la variante con NFC indica 494 × 464 × 452 mm. Estas medidas se conservan en `data/digital_twin/equipment_dimensions.json` como `OEM_MEASURED`. Ninguna medida interna se deriva de ellas como dato OEM.

Los originales permanecen en `data/manuals/` sin modificaciones. El inventario se genera con:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_oem_inventory
.\.venv\Scripts\python.exe -m scripts.build_twin_model
```

`oem_inventory.json` indexa las 437 páginas del Service Manual (encabezados, medidas mencionadas, imágenes incrustadas y menciones textuales por categoría), 26 figuras detectadas y 273 registros de piezas del Parts Catalog. El índice de páginas es un barrido documental, no una interpretación técnica aprobada de cada fotografía. Cada pieza extraída conserva documento, página, figura, número, nombre, cantidad, categoría, confianza y origen de medida. Las entradas topológicas no proporcionan posición métrica. Las menciones del Service Manual son evidencia textual para búsqueda, no piezas adicionales ni ubicaciones 3D.

## Topología inicial

`twin_model.json` contiene 34 nodos. Incluye cuerpo, cassette, cartridge simulado, cubiertas, panel, Reader/ADF, PCB, motor, rodillo y grupos `covers`, `rollers`, `hinges`, `tray`, `screws` y `guides` bajo `reader_adf`.

Referencias principales del catálogo:

| Conjunto | Figura | PDF | Ejemplos |
| --- | --- | ---: | --- |
| Cubiertas de iR 1643i | 100B | 22-23 | Rear Door `FM1-T491-000`, Right Cover `FM1-T493-000`, Left Cover `FM1-T492-000`, Rear Top Cover `FE8-6707-000` |
| Cassette y motor | 102A | 26-27 | Cassette `FM1-N488-000`, Main Motor `RM2-9531-000` |
| Panel | 130B | 42-43 | Control Panel `FM1-R686-020` |
| Reader/ADF | 160 | 44-45 | Rear Cover `FE8-3474-000`, Front Cover `FE8-3475-000`, separación `FM1-N703-000`, pickup `FC8-9251-000`, hinge `FM1-T197-000` (2), screw `XA9-0476-000` (15) |
| Reader | 400A | 49-50 | Reader Assembly `FM1-U532-000` |

El Parts Catalog figura 160 no fija posiciones métricas de sus piezas. El modelo usa prismas y cilindros como representaciones técnicas, no como CAD. Un part number del catálogo puede describir un conjunto que se dibuja con un solo volumen; la cantidad OEM se muestra como metadato y no como promesa de que haya igual cantidad de mallas. Los conectores del procedimiento son símbolos de la fotografía del Service Manual; no se asignó un part number sin respaldo.

## Estados y sincronización

Los 11 estados `STATE_00` a `STATE_10` expresan hitos del desmontaje. `STATE_00` representa equipo ensamblado. Seguridad no altera la geometría. Las seis preparaciones ocultan la pieza confirmada en orden. `STATE_07` señala acceso al ADF/Reader después de las preparaciones; comparte disposición física con `STATE_06`. Los pasos OEM posteriores representan liberación de fijaciones, cableado y extracción. El estado se calcula en el servidor desde los pasos confirmados, no desde una elección libre del visor.

Al cambiar de paso, la API `/api/digital-twin/state/ADF_READER_REMOVE` envía el estado y el componente activo. El Taller Digital lo resalta y reproduce un movimiento ilustrativo. La fotografía, texto, advertencias y PDF OEM siguen visibles en la guía. El modo de consulta del procedimiento no cambia el estado confirmado.

## Taller Digital y API

El visor usa WebGL local, sin biblioteca ni contenido externo. Arrastrar rota, rueda o gesto amplía, y tocar selecciona. Los controles permiten vista ensamblada, explotada y ocultar cubiertas. El buscador acepta nombre o part number. La selección muestra cantidad y página OEM. El botón **Ir al procedimiento** vuelve a la guía.

Endpoints autenticados:

- `GET /api/digital-twin`, `/dimensions`, `/inventory?figure=160`
- `GET /api/digital-twin/state/{procedure_id}`
- `GET /api/digital-twin/corrections`
- `PUT /api/digital-twin/corrections`
- `GET /api/digital-twin/target/{procedure_id}/{step_id}`

Las correcciones se guardan fuera del repositorio, en `%LOCALAPPDATA%\DataSystems\DS_TechVision\state\twin_corrections.json`, por usuario, modelo, componente y estado. Permiten escala, offset, rotación y offset de anchor. El visor aplica escala, desplazamiento y rotación; AR Simulation aplica el offset relativo al ancho del marcador. Quedan etiquetadas `PHYSICAL_VALIDATION_REQUIRED`. No se usa `PHYSICALLY_VALIDATED`.

## Limitaciones verificables

El contorno global se escala con las dimensiones OEM. Alto del cuerpo, grosores, posición del ADF, conectores, trayectorias y distancias de explosión son estimaciones visuales. El Parts Catalog es una topología, no un plano métrico. La orientación visual se diseñó para comprensión de la secuencia; no debe usarse para localizar fijaciones en una impresora real sin confirmar la foto OEM. No hay validación física ni metrológica.
