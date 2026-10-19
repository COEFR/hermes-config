# Wallets que NO son traders: receptoras, farms y fee-recipients de bots

Una dirección que te pasan puede no ser una persona operando. La pasada corta (25-70 tx) las deja
como «❓ SIN DATOS» o «0 compras / 0 ventas», y ahí está la trampa: eso **no** es «no hay información»,
es «no es un trader» — y hay que decirlo con la evidencia, no repetir la etiqueta automática. Si se
informa sin mirar, se termina valuando el bag de una wallet automatizada como si fuera un portafolio.

## Huellas (medidas, en orden de verificación)

| Chequeo | Llamada | Resultado que delata |
|---|---|---|
| ¿Existe la cuenta? | `getAccountInfo(addr, jsonParsed)` | `value: null` + `getBalance` 0 → nunca tuvo SOL, no pudo comprar ni pagar fees |
| ¿Se mueve su SOL? | muestreo de tx repartidas por **todas** las páginas | ΔSOL (0,0) siempre, aunque la wallet tenga cientos de cuentas de token |
| ¿Quién firma? | `accountKeys[].signer` (el `header` viene `None`) | `signer: False, writable: True` en casi todas → la wallet está **mencionada** en tx de otros |
| ¿Quién paga los fees? | `accountKeys[0]` agrupado | 2-3 cuentas distintas, todas bots de altísima frecuencia |
| Ritmo | total de firmas / días | p. ej. 10.000 tx en 13 días (~770/día) es ritmo de máquina, no de persona |
| Errores | `getSignaturesForAddress` → `err` | ~45% fallidas, casi todas `InsufficientFundsForRent` (intenta crear cuentas sin SOL para el rent) |
| Cuentas de token | `getTokenAccountsByOwner` | 200+ cuentas y muchas con saldo > 0: tokens **recibidos**, no comprados |

## El caso típico: receptora de un programa de fees

Si aparece en instrucciones del **programa de fees de pump.fun**
`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (`CollectCreatorFee`, `DistributeFeeToHolders`), y
además es no-firmante, es **destinataria** de una configuración de terceros (fee recipient/reparto a
holders), no la que opera. Los crankeadores de fees son bots: uno solo puede hacer 8.000 tx en ~20
minutos llamando `CollectCreatorFee` en bucle. El pagador de fees con capital (miles de SOL) y txs con
USDC + `DepositToken` apunta a un **operador de farm**: es el único vértice con plata real, y aun así
hay que auditarlo antes de prometer que sirve para copiar.

Contexto útil de esas tx: el **creador** de la moneda aparece en la misma instrucción (y RugCheck lo
devuelve en `creator`); los mints creados por pump.fun terminan en el sufijo vanity `pump`
(p. ej. `...7gbr5KZpump`). Los pares de cuentas que se ven en `DistributeFeeToHolders` son
[titular, su cuenta de token] — de ahí que cada dirección aparezca dos veces.

## Valuar el bag (y no confundirlo con rendimiento)

1. `getTokenAccountsByOwner` → mints con saldo > 0 (pueden ser 100+).
2. DexScreener: `priceUsd` del par con **más liquidez** de cada mint → valor nominal.
3. En el informe: aclarar que es **valor de tenencia**, no PnL ni capital operado, que el precio de un
   par ilíquido no es realizable, y que una wallet **sin SOL no puede ni pagar el fee de la venta**.
   Nunca presentarlo como «ganó X».

## Cómo cerrar el informe de una wallet así

- Veredicto en llano y primero: **«no es una wallet de trader: no compra, no vende, no tiene SOL»**.
- Los números que lo prueban (ritmo, % de errores, ΔSOL 0, cuentas de token, quién le paga los fees).
- Separar verificado de inferido: que sea receptora/en una configuración de terceros está **medido**;
  quién la controla y para qué es **inferencia** (el operador suele ser el bot que paga los fees).
- Qué NO hacer: cargarla al tracker. Un tracker de SOL/swaps sobre esta wallet es silencio y ruido.
- Y dejar dicho qué sigue: auditar el pagador con capital, o buscar candidatas por **compradores reales
  del pool** (que es el camino que sí discrimina trader de beneficiario).
