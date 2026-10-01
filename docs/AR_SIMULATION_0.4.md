# AR Simulation 0.4

## Uso

1. Iniciar la intervención guiada y completar seguridad y preparaciones hasta un paso OEM con AR.
2. Abrir **Abrir marcador** en otro monitor o tablet, o imprimir esa referencia. La página combina la foto OEM del paso y su QR.
3. En Android, iniciar la cámara y activar **AR Simulation**.
4. Apuntar al QR del paso. Se verá una representación 3D semitransparente, flecha, número de paso, acción y advertencia genérica de no tocar otras zonas. En los pasos documentados se muestran identificadores simulados T1-T4 para tornillos o C1-C4 para conectores; su posición sobre el QR no representa ubicación real.
5. Consultar siempre la foto OEM y el PDF para identificar la ubicación y ejecutar el trabajo.

El sistema detecta el valor QR exacto del paso activo mediante `BarcodeDetector`. El overlay se actualiza mientras el tracking esté fresco y se oculta al perderlo. Si el navegador no admite detección QR, se mantiene la imagen OEM y el texto. El video no se transmite al servidor. La página de referencia y sus imágenes requieren autenticación.

## Significado del overlay

El QR ancla una **simulación sobre una referencia visual**. No registra el volumen de la impresora ni reconoce piezas reales. El tamaño de la malla y su posición respecto del QR son aproximados. La etiqueta de pantalla dice `AR SIMULATION · GEOMETRÍA APROXIMADA`; el indicador de calibración dice `SIMULACIÓN NO CALIBRADA`. La flecha y las zonas indicativas ayudan a leer la acción, pero no sustituyen la fotografía OEM.

El modo AR de marcador de 0.3 permanece disponible al desactivar AR Simulation. Ese modo usa una calibración local por paso, todavía sin validación física. En ambos modos, al perder tracking se limpia el overlay. Si la cámara no puede iniciarse, la guía continúa con imagen y texto OEM.

## Componentes y movimientos

El visor WebGL dibuja cubiertas como prismas, rodillos y tornillos como cilindros, PCB como placa y conjuntos como prismas. El paso activo puede declarar `REMOVE_LINEAR`, `ROTATE_OPEN`, `UNSCREW`, `DISCONNECT`, `LIFT` o `SLIDE`. Las direcciones y distancias son ilustrativas y están separadas de los datos OEM. La vista explotada anima la separación al seleccionar el modo correspondiente.

## Validación

Las pruebas automatizadas comprueban escala, jerarquía, part numbers, estados, persistencia y contratos del overlay. Se probó la interfaz en Chrome headless con viewport de escritorio y Android, incluyendo aparición y retirada del overlay con tracking simulado. No se probó una cámara Android física ni una Canon imageRUNNER 1643i real. Ambas validaciones permanecen pendientes.
