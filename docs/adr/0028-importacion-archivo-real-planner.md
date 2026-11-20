# ADR 0028 — Importación del archivo real de la planner y exportación para scripts

- **Estado:** Aceptado
- **Fecha:** 2026-11-20
- **Complementa:** ADR 0009, ADR 0018, ADR 0019 (límites) y ADR 0026 (exportación de la planner)

## Contexto

Los ADR 0009 y 0018 definieron la importación con nombres de columna abreviados. El archivo real de la planner tiene una estructura concreta: dos hojas de invitados, hojas que no son de invitados, título en la fila 1, encabezados largos en la fila 2, la columna A vacía, ~220 filas con formato y solo unas decenas con datos, números como decimales y **sin columna Código INV**. Además, Mayra quiere usar la exportación para su propio script del mensaje del día de la boda.

## Decisión

### Estructura que se reconoce
- **Hojas:** solo las que tienen una fila de encabezados con «Nombre Invitado» (por ejemplo «Lista de invitados», del novio, y «Copia de Lista de invitados», de la novia). Las demás (presupuestos, playlist, personas importantes) se ignoran. Si hay varias, se elige la hoja al importar (`hoja`).
- **Encabezados exactos** (columnas B a O del archivo real): «No.», «Nombre Invitado», «# Pases», «Teléfono/Celular», «Nombre Contacto Alterno», «Tel/Celular   de contacto alterno» (con tres espacios), «Infante (menor a 2 años no aplica asiento ni A&B)», «Adultos», «# de Niños (aplica asiento y alimentos)», «Invitado de», «¿Asistirá?», «Pases confirmados», «# de mesa», «Comentario». Opcionales: «Código INV», «Mensaje del invitado», «Grupo», «Rol», «Alergias».
- La fila de encabezados se busca en las primeras 10 filas y las columnas se ubican por su encabezado. Al comparar se quitan los espacios de los extremos y los espacios repetidos se cuentan como uno; cualquier otra diferencia cuenta.
- Las filas vacías se ignoran. `2.0` se lee como `2`. Los teléfonos pueden venir como número (`4441234567.0`) o como texto con espacios.

### Reglas de importación
- **Lado por defecto:** «Invitado de» suele venir vacío; al importar se elige un lado por defecto (`lado_por_defecto`, normalmente el de la hoja) que solo se usa cuando la celda está vacía.
- **«Adultos» vacío** es error de fila (`adultos_faltante`): no se inventa a partir de «# Pases».
- **«# Pases»** solo cuenta en las altas, donde se guarda como el original de la planner. En las actualizaciones se ignora: la marca de revisión se recalcula contra el original guardado. Así, reimportar el archivo exportado (que trae «# Pases» calculado) no cambia nada.
- **Motivos de revisión al actualizar:** un valor inválido agrega el motivo; un valor válido lo quita; una celda vacía lo conserva. El teléfono solo se da por válido si los dos teléfonos vienen llenos y válidos.
- **«Nombre Invitado» con «+»** se importa tal cual, con el aviso `nombre_con_varios`: «Este nombre es el que verá el invitado («Invitación para …»). Conviene acortarlo antes de enviar enlaces.»
- **Todo o nada:** aplicar un archivo con cualquier error de fila responde `409 archivo_con_errores` y no escribe nada.
- **El archivo va en el cuerpo de la petición** (sin multipart).

### Duplicados y forma de trabajo
- La hoja de la planner no trae Código INV, así que cada fila es un alta. Las filas cuyo nombre ya existe (o se repite en el archivo) llevan el aviso `posible_duplicado`, y la vista previa muestra arriba: «N de M filas parecen ya importadas…» (se importan igual, ADR 0018).
- **Regla de trabajo:** cada hoja de la planner se importa **una vez**. Después, los cambios se hacen en el panel o reimportando **el archivo exportado**, que sí trae Código INV.

### Exportación
- Las 19 columnas, con los **encabezados reales** de la planner, iguales para novios y planner (ADR 0026). Sin enlaces ni tokens.
- **Para el script del día de la boda:** teléfonos en E.164 (`+52…`) como texto, autofiltro y fila de encabezados fija (se filtra «¿Asistirá?» = Sí), y la opción `solo_confirmados` que exporta solo las invitaciones confirmadas.
- **Protección contra fórmulas:** las celdas de texto que empiezan con `=`, `+`, `-`, `@`, tabulador o retorno se escriben con `'` delante, salvo los teléfonos E.164 que genera la API; la importación quita ese `'`.

### Límites y archivos maliciosos
- Archivo de 2 MB como máximo (`MAX_IMPORT_FILE`), solo `.xlsx` y `.csv` (por su firma); `.xls` y `.xlsm` se rechazan.
- Antes de abrir un `.xlsx`: como máximo 200 entradas, 30 MB descomprimidos y una proporción de compresión de 200 por entrada (bomba ZIP); sin entradas cifradas, macros, rutas con `..` ni XML con `<!DOCTYPE>` o `<!ENTITY>`.
- openpyxl en modo solo lectura, sin evaluar fórmulas ni seguir vínculos externos, con defusedxml; como máximo 5,000 filas recorridas, 1,000 filas con datos y 30 columnas.

## Consecuencias

- La planner sigue usando su formato sin cambios; el panel lo entiende tal cual.
- Reimportar la hoja original de la planner duplicaría invitaciones; la vista previa lo advierte y la regla de trabajo lo evita.
- Los archivos exportados contienen teléfonos y alergias: van fuera del repositorio y se borran o recortan el 5 abr 2027 (ADR 0010).
