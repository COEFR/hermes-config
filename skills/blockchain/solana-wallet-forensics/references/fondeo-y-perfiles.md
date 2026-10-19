# Fondeo de wallets y perfiles: trampas medidas

- `funder_de(w, n)` mira las ÚLTIMAS n tx: en una wallet que ya operó devuelve un pagador **reciente** (un pool, un bot) y produce falsos "fondeo compartido". Para saber quién la financió al nacer hay que leer las tx **MÁS VIEJAS** y quedarse con la cuenta que **envió** SOL (descartar la que lo recibió, típico de un pool/AMM).
- Si el historial es más largo que lo que se paginó, responder **"sin determinar"** en vez de inventar un fondeador leyendo un tramo del medio del historial.
- `sigs_mas_viejas(mint, cuantas, max_paginas)` devuelve una **tupla** `(firmas, páginas, total)` — hay que desempaquetarla, y `total` sirve para detectar que no se llegó al origen (si `total >= max_paginas*1000`, no se alcanzó el arranque).
- El perfil de una wallet (¿persona o granja de bots?) hay que **cachearlo en un archivo (7 días)**: recalcularlo en cada pasada hace que la etiqueta se dé vuelta cuando falla la red, y una granja ya marcada vuelve a "grupo de personas".
- Firmas de granja: wallets **frescas** (sin historial) y/o **fondeador compartido** entre los miembros. Un pool/AMM compartido NO es un fondeador compartido.
- Ojo con las direcciones de vanidad (ej. prefijo `sssss…`): no son personas, son cuentas operativas de un servicio.
- `getSignaturesForAddress` con `limit` > 1000 lo rechaza el RPC: paginar de a 1000.
- DexScreener responde **403 sin User-Agent propio**; su respuesta es un dict con `pairs` y el mejor par se elige por liquidez (no es una lista).
