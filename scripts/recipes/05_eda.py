CELLS = [
{"type": "markdown", "source": r"""
# 05 · Análisis Exploratorio de Datos (EDA) de punta a punta

El EDA no es "correr `.describe()` y graficar histogramas" — es un proceso
sistemático para entender la calidad de los datos, sus patrones y sus riesgos
**antes** de modelar. Este módulo replica el flujo real que seguirías con un
dataset nuevo en el trabajo.

**Dataset:** `credito_solicitudes.csv` (con nulos y duplicados intencionales
para practicar limpieza real).

## Contenido
1. Primer contacto: shape, tipos, memoria
2. Duplicados: detectar y decidir qué hacer
3. Valores nulos: patrón (¿MCAR/MAR/MNAR?) y estrategia de imputación
4. Outliers: IQR, z-score, y por qué el contexto de negocio manda
5. Análisis univariado y bivariado sistemático
6. Feature engineering exploratorio
7. Checklist de reporte de calidad de datos
"""},

{"type": "code", "source": r"""
import numpy as np
import pandas as pd

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)

df = pd.read_csv("data/credito_solicitudes.csv", parse_dates=["fecha_solicitud"])
df.shape
"""},

{"type": "markdown", "source": r"""
## 1. Primer contacto

Antes de cualquier análisis: ¿qué tipos tiene cada columna?, ¿cuánta memoria
usa?, ¿los tipos son los que esperarías (fechas como datetime, no como
string)?
"""},

{"type": "code", "source": r"""
df.info()
"""},

{"type": "code", "source": r"""
resumen_columnas = pd.DataFrame({
    "dtype": df.dtypes,
    "n_nulos": df.isna().sum(),
    "pct_nulos": (df.isna().mean() * 100).round(1),
    "n_unicos": df.nunique(),
})
resumen_columnas
"""},

{"type": "markdown", "source": r"""
## 2. Duplicados

Un duplicado exacto en un ID que debería ser único es una señal de un bug en
el pipeline de ingesta (doble carga, join mal hecho). Se detecta y se decide
explícitamente si eliminar o investigar el origen.
"""},

{"type": "code", "source": r"""
n_dup_completos = df.duplicated().sum()
n_dup_por_id = df.duplicated(subset="solicitud_id").sum()

print(f"Filas 100% duplicadas: {n_dup_completos}")
print(f"solicitud_id duplicados: {n_dup_por_id}")

if n_dup_por_id > 0:
    print("\nEjemplo de duplicado:")
    id_dup = df.loc[df.duplicated(subset="solicitud_id", keep=False), "solicitud_id"].iloc[0]
    print(df[df["solicitud_id"] == id_dup])

df = df.drop_duplicates(subset="solicitud_id", keep="first")
print(f"\nShape tras deduplicar: {df.shape}")
"""},

{"type": "markdown", "source": r"""
## 3. Valores nulos: patrón antes que imputación

Antes de imputar hay que entender **por qué** falta el dato:

- **MCAR** (Missing Completely At Random): la ausencia no depende de nada —
  seguro de imputar con media/mediana.
- **MAR** (Missing At Random): la ausencia depende de OTRA variable observada
  — imputar condicionando en esa variable (ej. mediana por grupo).
- **MNAR** (Missing Not At Random): la ausencia depende del propio valor
  faltante (ej. gente con ingresos muy altos no los reporta) — la imputación
  simple sesga el análisis; considera un indicador de "faltante" como feature.
"""},

{"type": "code", "source": r"""
# ¿El nulo en ingreso_mensual se relaciona con otras variables? (evidencia de MAR vs MCAR)
df["ingreso_es_nulo"] = df["ingreso_mensual"].isna()

comparacion = df.groupby("ingreso_es_nulo", observed=True).agg(
    buro_score_prom=("buro_score", "mean"),
    tasa_default=("default_90d", "mean"),
    n=("solicitud_id", "count"),
).round(3)
comparacion
"""},

{"type": "code", "source": r"""
# Si no hay diferencia sistemática notable -> tratamos como MCAR/MAR leve: imputar mediana POR SECTOR
# (mejor que mediana global: respeta que sectores tienen niveles de ingreso distintos)
mediana_por_sector = df.groupby("sector", observed=True)["ingreso_mensual"].transform("median")
df["ingreso_mensual_imputado"] = df["ingreso_mensual"].fillna(mediana_por_sector)

# buro_score: mantenemos el nulo explícito -> "sin historial crediticio" es información real,
# no ruido a rellenar (candidato a MNAR: quien no tiene score suele ser cliente nuevo)
df["sin_historial_crediticio"] = df["buro_score"].isna().astype(int)

print(f"Nulos en ingreso_mensual: {df['ingreso_mensual'].isna().sum()} -> {df['ingreso_mensual_imputado'].isna().sum()} tras imputar")
print(f"Solicitudes sin historial crediticio: {df['sin_historial_crediticio'].sum()} ({df['sin_historial_crediticio'].mean():.1%})")
"""},

{"type": "markdown", "source": r"""
## 4. Outliers: IQR, z-score, y criterio de negocio

Un outlier estadístico no siempre es un error de datos — puede ser un cliente
corporativo legítimo. La regla es: **detectar con estadística, decidir con
contexto de negocio.**
"""},

{"type": "code", "source": r"""
def detectar_outliers_iqr(serie, k=1.5):
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    limite_inf, limite_sup = q1 - k * iqr, q3 + k * iqr
    return (serie < limite_inf) | (serie > limite_sup), (limite_inf, limite_sup)

outliers_monto, (lim_inf, lim_sup) = detectar_outliers_iqr(df["monto_solicitado"])
print(f"Límites IQR (k=1.5): (${lim_inf:,.0f}, ${lim_sup:,.0f})")
print(f"Outliers detectados: {outliers_monto.sum()} ({outliers_monto.mean():.1%} de las filas)")

# Z-score modificado (robusto, basado en mediana) -> mejor que z-score clásico con datos sesgados
mediana = df["monto_solicitado"].median()
mad = (df["monto_solicitado"] - mediana).abs().median()  # median absolute deviation
z_robusto = 0.6745 * (df["monto_solicitado"] - mediana) / mad
outliers_z = z_robusto.abs() > 3.5

print(f"Outliers por z-score robusto: {outliers_z.sum()} ({outliers_z.mean():.1%})")
print(f"Coinciden ambos métodos en: {(outliers_monto & outliers_z).sum()} filas")
"""},

{"type": "code", "source": r"""
# Contexto de negocio: ¿los outliers de monto son un segmento coherente (empresas grandes)
# o basura de captura (montos absurdos, ej. de más de $50M)?
top_outliers = df.loc[outliers_monto].sort_values("monto_solicitado", ascending=False)
print(top_outliers[["sector", "ingreso_mensual", "monto_solicitado", "buro_score", "antiguedad_empresa_anios"]].head(5))
print("\n-> Los montos altos vienen acompañados de ingresos altos y empresas más establecidas:")
print("   parecen un segmento real (empresas grandes), no errores de captura. NO se eliminan;")
print("   se documentan como segmento aparte para el modelado.")
"""},

{"type": "markdown", "source": r"""
## 5. Análisis univariado y bivariado sistemático

Un checklist rápido y repetible en vez de graficar al azar:
- Univariado numérico: distribución (forma, sesgo) por variable.
- Univariado categórico: frecuencias, ¿hay categorías raras con pocos casos?
- Bivariado: cada predictor candidato vs. la variable objetivo.
"""},

{"type": "code", "source": r"""
# Univariado categórico: frecuencias + detección de categorías con muy pocos casos
for col in ["sector", "plazo_meses"]:
    frecuencias = df[col].value_counts(normalize=True).mul(100).round(1)
    print(f"--- {col} ---")
    print(frecuencias)
    categorias_raras = frecuencias[frecuencias < 3]
    if not categorias_raras.empty:
        print(f"  Categorías <3% del total (candidatas a agrupar en 'Otros'): {list(categorias_raras.index)}")
    print()
"""},

{"type": "code", "source": r"""
# Bivariado sistemático: tasa de default por bin de cada variable numérica candidata
variables_numericas = ["buro_score", "ingreso_mensual_imputado", "antiguedad_empresa_anios", "num_creditos_previos"]

for col in variables_numericas:
    bins = pd.qcut(df[col], q=4, duplicates="drop")
    tasa_por_bin = df.groupby(bins, observed=True)["default_90d"].agg(["mean", "count"])
    print(f"--- Tasa de default por cuartil de {col} ---")
    print(tasa_por_bin.round(3))
    print()
"""},

{"type": "markdown", "source": r"""
## 6. Feature engineering exploratorio

El EDA no solo detecta problemas — genera hipótesis de features que
alimentarán el módulo de Machine Learning.
"""},

{"type": "code", "source": r"""
df["dti"] = df["deuda_actual"] / (df["ingreso_mensual_imputado"] + 1)
df["monto_sobre_ingreso"] = df["monto_solicitado"] / (df["ingreso_mensual_imputado"] + 1)
df["cuota_mensual_aprox"] = df["monto_solicitado"] * (df["tasa_interes"] / 12) / (1 - (1 + df["tasa_interes"] / 12) ** (-df["plazo_meses"]))
df["carga_deuda_total"] = (df["cuota_mensual_aprox"] + df["deuda_actual"] * 0.03) / (df["ingreso_mensual_imputado"] + 1)

nuevas_features = ["dti", "monto_sobre_ingreso", "cuota_mensual_aprox", "carga_deuda_total"]
correlacion_con_target = df[nuevas_features + ["default_90d"]].corr(numeric_only=True)["default_90d"].drop("default_90d")
print("Correlación de nuevas features con default_90d:")
print(correlacion_con_target.sort_values(ascending=False).round(3))
"""},

{"type": "markdown", "source": r"""
## 7. Checklist de reporte de calidad de datos

Antes de pasar el dataset a modelado, un analista senior documenta:
"""},

{"type": "code", "source": r"""
reporte_calidad = {
    "filas_originales": 6015,
    "filas_tras_deduplicar": len(df),
    "columnas_con_nulos": list(resumen_columnas.loc[resumen_columnas["n_nulos"] > 0].index),
    "estrategia_nulos": {
        "ingreso_mensual": "imputado con mediana por sector",
        "buro_score": "mantenido como nulo + flag 'sin_historial_crediticio'",
    },
    "outliers_detectados_monto": int(outliers_monto.sum()),
    "decision_outliers": "conservados (segmento real de empresas grandes)",
    "features_nuevas": nuevas_features,
    "tasa_default_global": round(df["default_90d"].mean(), 4),
}
import json
print(json.dumps(reporte_calidad, indent=2, ensure_ascii=False))
"""},

{"type": "markdown", "source": r"""
## Resumen y siguientes pasos

- El orden importa: primer contacto → duplicados → nulos (con hipótesis de
  patrón) → outliers (con criterio de negocio) → univariado/bivariado →
  feature engineering.
- Nunca imputes sin antes preguntarte si el nulo mismo es información
  (`sin_historial_crediticio` es más útil que rellenarlo a ciegas).
- Documenta cada decisión de limpieza — el reporte de calidad es el contrato
  entre EDA y modelado.

**Siguiente módulo:** `06_visualizacion_datos.ipynb` — convertir estos
hallazgos en gráficas que comuniquen, no solo que "se vean bonitas".
"""},
]
