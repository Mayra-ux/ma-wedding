# ADR 0022 — Implementación de tokens y rotación de llaves

- **Estado:** Aceptado
- **Fecha:** 2026-11-03
- **Complementa:** ADR 0019 (Tokens) y ADR 0008

## Contexto

El ADR 0019 fija HMAC-SHA-256 para buscar el token, AES-256-GCM para la copia cifrada con identificador de llave, y una rotación en tres pasos que no corta los enlaces enviados. Al implementar la fase I-3 quedaron por precisar: cómo seguir encontrando los enlaces mientras cambia la llave de hash, cómo impedir que una copia cifrada se reutilice en otra fila, el tamaño exacto de la copia y cómo evitar que el token en claro termine en un log por accidente.

## Decisión

- **Rotación de la llave de hash sin cortes:** la llave anterior va en `TOKEN_HASH_KEY_PREVIOUS`, solo durante la rotación. La búsqueda prueba la llave actual y después la anterior, así que los enlaces siguen funcionando entre el reinicio y `rotate-keys`. Al terminar se quita la variable.
- **Datos asociados (AAD) de la copia cifrada:** `enlace|v1|<invitacion_id>|<id_llave>`. Una copia movida a otra fila o con otro id de llave no se descifra.
- **Tamaño de la copia:** exactamente 44 bytes (nonce 12 + cifrado 16 + etiqueta 16), garantizado en la DB (migración 0002).
- **Token en memoria:** vive en `TokenEnClaro`, cuyo `repr`, `str` y `format` lo ocultan; no se puede serializar.
- **Llaves fuera del repositorio:** `.env.example` solo lleva `__GENERAR__`. El comando `generar-llaves` las escribe en un `.env` sin imprimirlas y se niega a pisar llaves existentes.

Procedimiento operativo y variables: doc 11, «Enlaces y llaves de tokens».

## Consecuencias

- La rotación completa (cifrado y hash) no corta ningún enlace enviado.
- Copiar una copia cifrada de una fila a otra no sirve para suplantar otra invitación.
- Se agrega una variable de entorno opcional (`TOKEN_HASH_KEY_PREVIOUS`).
