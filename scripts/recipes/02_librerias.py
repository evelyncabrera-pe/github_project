CELLS = [
{"type": "markdown", "source": r"""
# 02 · Librerías clave: NumPy y Pandas a nivel avanzado

Este módulo asume que ya conoces la sintaxis básica de pandas (indexing,
`.loc`/`.iloc`, filtros). El foco aquí es **rendimiento, vectorización y
patrones de manipulación que un analista senior usa a diario**: joins
complejos, pivots, ventanas móviles, y cuándo NumPy puro le gana a pandas.

**Datasets:** `credito_solicitudes.csv` y `ventas_ecommerce_tech.csv`.

## Contenido
1. Vectorización con NumPy: por qué evitar loops
2. `groupby` avanzado: múltiples agregaciones, `transform` vs `apply`
3. Merge / join: tipos, validación de cardinalidad, detectar duplicados
4. Reshape: `pivot_table`, `melt`, `stack`/`unstack`
5. Ventanas móviles y series de tiempo con `rolling`/`resample`
6. Performance: `category`, `query`, `eval`, cuándo migrar a Polars
"""},

{"type": "code", "source": r"""
import numpy as np
import pandas as pd

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 120)

df = pd.read_csv("data/credito_solicitudes.csv", parse_dates=["fecha_solicitud"])
ventas = pd.read_csv("data/ventas_ecommerce_tech.csv", parse_dates=["fecha"])
df.shape, ventas.shape
"""},

{"type": "markdown", "source": r"""
## 1. Vectorización con NumPy

La regla de oro: **si estás escribiendo un `for` sobre filas de un DataFrame,
casi siempre hay una forma vectorizada.** NumPy opera sobre arrays completos en
C, evitando el overhead del intérprete de Python por elemento.
"""},

{"type": "code", "source": r"""
import time

ingresos = df["ingreso_mensual"].fillna(df["ingreso_mensual"].median()).to_numpy()
deuda = df["deuda_actual"].to_numpy()

# Forma lenta: loop en Python puro
t0 = time.perf_counter()
dti_loop = [d / (i + 1) for d, i in zip(deuda, ingresos)]
t_loop = time.perf_counter() - t0

# Forma vectorizada: NumPy opera sobre el array completo
t0 = time.perf_counter()
dti_vec = deuda / (ingresos + 1)
t_vec = time.perf_counter() - t0

print(f"Loop Python:  {t_loop*1000:.2f} ms")
print(f"Vectorizado:  {t_vec*1000:.2f} ms")
print(f"Speedup:      {t_loop/t_vec:.1f}x")
assert np.allclose(dti_loop, dti_vec)
"""},

{"type": "code", "source": r"""
# np.select: la forma correcta de hacer un if/elif/else vectorizado
condiciones = [
    df["buro_score"] >= 700,
    df["buro_score"] >= 600,
    df["buro_score"] >= 500,
]
categorias = ["A - Bajo riesgo", "B - Riesgo medio", "C - Riesgo alto"]
df["categoria_riesgo"] = np.select(condiciones, categorias, default="D - Muy alto riesgo / sin score")

df["categoria_riesgo"].value_counts()
"""},

{"type": "markdown", "source": r"""
## 2. `groupby` avanzado

Tres patrones que se usan constantemente en análisis de negocio:

- **Múltiples agregaciones nombradas** con `.agg(**kwargs)` — output limpio, sin
  MultiIndex feo en columnas.
- **`.transform()`** cuando quieres el resultado agregado alineado al tamaño
  original del DataFrame (ej. "monto vs. promedio de su sector").
- **`.apply()`** solo cuando la lógica no se puede expresar con `.agg`/`.transform`
  (más lento, más flexible).
"""},

{"type": "code", "source": r"""
resumen_sector = df.groupby("sector", observed=True).agg(
    n_solicitudes=("solicitud_id", "count"),
    monto_promedio=("monto_solicitado", "mean"),
    tasa_default=("default_90d", "mean"),
    score_promedio=("buro_score", "mean"),
).round(2).sort_values("tasa_default", ascending=False)

resumen_sector
"""},

{"type": "code", "source": r"""
# transform: comparar cada solicitud contra el promedio de SU sector, sin perder filas
df["monto_promedio_sector"] = df.groupby("sector", observed=True)["monto_solicitado"].transform("mean")
df["desviacion_vs_sector"] = df["monto_solicitado"] / df["monto_promedio_sector"] - 1

df[["sector", "monto_solicitado", "monto_promedio_sector", "desviacion_vs_sector"]].head()
"""},

{"type": "markdown", "source": r"""
## 3. Merge / join: validación de cardinalidad

El bug más común en pipelines de datos es un merge que **explota filas**
silenciosamente por una relación 1:muchos no esperada. `pd.merge(..., validate=...)`
lanza un error inmediato en vez de dejarte con un DataFrame corrupto.
"""},

{"type": "code", "source": r"""
resumen_riesgo_sector = df.groupby("sector", observed=True)["buro_score"].mean().rename("score_prom_sector").reset_index()

# validate="many_to_one": cada fila de df debe matchear a lo más 1 fila de resumen_riesgo_sector
df_enriquecido = df.merge(resumen_riesgo_sector, on="sector", how="left", validate="many_to_one")
print(f"Filas antes: {len(df):,} | Filas después del merge: {len(df_enriquecido):,}  (deben coincidir)")

# Ejemplo de lo que detecta validate: si hubiera duplicados en la tabla de la derecha, esto fallaría
try:
    dup_sector = pd.concat([resumen_riesgo_sector, resumen_riesgo_sector.iloc[[0]]])  # sector duplicado a propósito
    df.merge(dup_sector, on="sector", how="left", validate="many_to_one")
except pd.errors.MergeError as e:
    print(f"\nMergeError capturado (como se esperaba): {e}")
"""},

{"type": "markdown", "source": r"""
## 4. Reshape: `pivot_table`, `melt`, `stack`/`unstack`

`ventas_ecommerce_tech.csv` está en formato "largo" (una fila por
fecha-categoría-región). Para reportes ejecutivos normalmente se necesita
formato "ancho" — y viceversa para alimentar modelos o gráficas de series
múltiples.
"""},

{"type": "code", "source": r"""
# Largo -> ancho: ingresos totales por categoría (filas) y región (columnas)
tabla_pivote = ventas.pivot_table(
    index="categoria",
    columns="region",
    values="ingresos",
    aggfunc="sum",
    margins=True,
    margins_name="Total",
).round(0)

tabla_pivote
"""},

{"type": "code", "source": r"""
# Ancho -> largo con melt: útil para pasar de "reporte" a "formato tidy" para graficar/modelar
ventas_mensuales = (
    ventas.assign(mes=ventas["fecha"].dt.to_period("M").astype(str))
    .pivot_table(index="mes", columns="categoria", values="ingresos", aggfunc="sum")
)
ventas_mensuales_tidy = ventas_mensuales.reset_index().melt(
    id_vars="mes", var_name="categoria", value_name="ingresos"
)
print(ventas_mensuales.shape, "-> melt ->", ventas_mensuales_tidy.shape)
ventas_mensuales_tidy.head()
"""},

{"type": "markdown", "source": r"""
## 5. Ventanas móviles y series de tiempo

`rolling` (ventana deslizante) y `resample` (re-muestreo por frecuencia de
tiempo) son la base de cualquier análisis de tendencia o estacionalidad antes
de pasar a un modelo de forecasting.
"""},

{"type": "code", "source": r"""
ventas_diarias = ventas.groupby("fecha", as_index=True)["ingresos"].sum().sort_index()

resumen_tendencia = pd.DataFrame({
    "ingresos": ventas_diarias,
    "media_movil_7d": ventas_diarias.rolling(window=7, min_periods=1).mean(),
    "media_movil_30d": ventas_diarias.rolling(window=30, min_periods=1).mean(),
})

# resample: agregación mensual real (respeta calendario, no solo "cada 30 filas")
ingresos_mensuales = ventas_diarias.resample("ME").sum()

print(resumen_tendencia.tail(3))
print("\nÚltimos 3 meses (resample ME):")
print(ingresos_mensuales.tail(3))
"""},

{"type": "markdown", "source": r"""
## 6. Performance: `category`, `query`, `eval`, y cuándo migrar a Polars

- **`astype("category")`** en columnas de baja cardinalidad (sector, región):
  reduce memoria y acelera `groupby`.
- **`df.query()` / `df.eval()`**: evalúan expresiones con un motor optimizado
  (numexpr) — más rápido y legible que encadenar máscaras booleanas en
  DataFrames grandes.
- **Polars**: cuando un pipeline de pandas empieza a tardar minutos (varios GB,
  muchos joins/groupbys), Polars (API similar, backend en Rust, paralelo por
  defecto) suele dar 5-30x de mejora sin reescribir toda la lógica.
"""},

{"type": "code", "source": r"""
# query/eval: legible y rápido para filtros/columnas derivadas complejas
alto_riesgo = df.query("buro_score < 550 and monto_solicitado > 300_000 and sector == 'Tecnología'")
print(f"Solicitudes de alto riesgo en Tecnología: {len(alto_riesgo)}")

df_eval = df.eval("ratio_monto_ingreso = monto_solicitado / ingreso_mensual")
df_eval[["monto_solicitado", "ingreso_mensual", "ratio_monto_ingreso"]].head(3)
"""},

{"type": "markdown", "source": r"""
```python
# Equivalente en Polars (referencia, no ejecutado aquí) — sintaxis "lazy" para
# que el optimizador de queries decida el plan de ejecución antes de correrlo:
import polars as pl

resultado = (
    pl.scan_csv("data/ventas_ecommerce_tech.csv", try_parse_dates=True)
    .filter(pl.col("categoria") == "Laptops")
    .group_by("region")
    .agg(pl.col("ingresos").sum().alias("ingresos_totales"))
    .sort("ingresos_totales", descending=True)
    .collect()  # aquí se ejecuta el plan optimizado
)
```
"""},

{"type": "markdown", "source": r"""
## Resumen y siguientes pasos

- Vectoriza con NumPy/`np.select` antes de escribir loops o `.apply(axis=1)`.
- `.agg()` para agregaciones limpias, `.transform()` para comparar contra el
  grupo sin perder filas.
- Siempre usa `validate=` en merges de producción — detecta explosiones de
  filas antes de que lleguen a un reporte.
- `pivot_table`/`melt` son las dos caras de la misma moneda: reporte ejecutivo
  vs. formato tidy para modelar/graficar.
- Si pandas se vuelve el cuello de botella, Polars suele ser el siguiente paso
  antes de saltar a Spark.

**Siguiente módulo:** `03_sql_bases_datos.ipynb` — SQL y su integración con pandas.
"""},
]
