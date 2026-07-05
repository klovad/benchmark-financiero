# Diccionario de datos

Fuente: portal CAPCOL de la Superintendencia de Bancos de Ecuador (bancos privados),
reportes de cartera (antes "colocaciones") y depósitos (antes "captaciones").
Periodicidad mensual, alcance cargado: 2021-01 a 2025-12.

## marts.dim_fecha
| Columna | Tipo | Descripción |
|---|---|---|
| fecha_id | int (YYYYMM) | Llave sustituta de fecha |
| fecha | date | Fin de mes de corte |
| anio, mes, trimestre | int | Derivados de fecha |
| nombre_mes | text | Nombre del mes en español |

## marts.dim_banco
| banco_id | serial | Llave sustituta |
| banco | text | Nombre del banco privado tal como lo reporta Superbancos. **Nota de calidad**: no hay una tabla de alias entre años; un mismo banco podría aparecer con variantes de nombre si Superbancos cambió su razón social (no detectado en el rango 2021-2025 cargado). |

## marts.dim_canton
| canton_id | serial | Llave sustituta |
| canton, provincia | text | Ubicación de la oficina donde se registró la operación (no la residencia del cliente) |
| region | text | Costa / Sierra / Oriente / Insular, derivada de la provincia (no viene en el archivo de cartera; se calcula) |

## marts.dim_producto_cartera
| tipo_credito | text | comercial, consumo, inmobiliario, microcredito, vivienda_interes_publico, educativo (categorías oficiales de Superbancos) |
| estado_cartera | text | por_vencer, no_devenga_intereses, vencida |

## marts.dim_producto_deposito
| tipo_deposito | text | Categoría de depósito tal como la reporta Superbancos (13 valores: depósitos monetarios con/sin interés, ahorro, cuenta básica, buckets de plazo por rango de días, garantía, restringidos, por confirmar) |

## marts.fact_cartera (grano: fecha x banco x cantón x tipo_credito x estado_cartera)
| saldo | numeric | Saldo en USD |
| saldo_x_tasa, tasa_ponderada | numeric, NULL en v1 | **El archivo fuente de cartera no incluye tasa de interés** (confirmado contra la ficha metodológica y el archivo real); columnas reservadas para cuando se incorpore una fuente de tasas |

## marts.fact_depositos (grano: fecha x banco x cantón x tipo_deposito)
| saldo | numeric | Saldo en USD |
| numero_cuentas, numero_clientes | bigint | Sumados desde el detalle por cuenta contable (columna CUENTA del origen, no conservada en marts) |
| saldo_x_tasa, tasa_ponderada | numeric, NULL en v1 | Igual que en cartera: la fuente no trae tasa |

## Decisiones de modelado relevantes
- **Sin tasas de interés en v1**: decisión explícita del usuario tras confirmar que CAPCOL no las reporta (ver docs/architecture.md).
- **Agregación de duplicados**: el origen trae detalle por cuenta contable / oficina; se agrega (SUM) al grano de staging para no perder saldo (ver `etl/transform/parse_cartera.py` y `parse_depositos.py`).
- **Alcance**: solo bancos privados (`tipo_entidad = 'BANCO PRIVADO'`), tal como pide el README del proyecto.
