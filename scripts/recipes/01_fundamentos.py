CELLS = [
{"type": "markdown", "source": r"""
# 01 · Fundamentos de Python para análisis de datos

**Nivel:** referencia senior — no es un curso de sintaxis básica, sino los patrones
que un analista de datos con experiencia usa todos los días: tipado, manejo de
rutas, lectura de múltiples formatos, control de errores en ingestión de datos
y consumo de APIs.

**Dataset base:** `data/credito_solicitudes.csv` (solicitudes de crédito fintech).

## Contenido
1. Entorno y estilo (type hints, `pathlib`, f-strings avanzados)
2. Estructuras de datos idiomáticas (comprehensions, `dataclasses`, `Counter`)
3. Lectura robusta de CSV / Excel / JSON
4. Consumo de APIs REST con `requests`
5. Manejo de errores y logging en pipelines de ingestión
"""},

{"type": "markdown", "source": r"""
## 1. Entorno y estilo

Un analista senior escribe Python que otros (y su "yo" de dentro de 6 meses)
puedan mantener. Tres hábitos que marcan la diferencia frente a código de nivel
junior:

- **Type hints** en funciones que se reutilizan (documentan intención, habilitan
  autocompletado y catch de errores con `mypy`/`pyright`).
- **`pathlib.Path`** en vez de concatenar strings para rutas — es portable entre
  SO y evita bugs de separadores `/` vs `\`.
- **f-strings con especificadores de formato** para números (`:,`, `:.2%`) en vez
  de redondear a mano.
"""},

{"type": "code", "source": r"""
from pathlib import Path
from dataclasses import dataclass, field
import pandas as pd

DATA_DIR = Path("data")

def cargar_credito(path: Path = DATA_DIR / "credito_solicitudes.csv") -> pd.DataFrame:
    '''Carga y tipa el dataset de solicitudes de crédito.'''
    df = pd.read_csv(path, parse_dates=["fecha_solicitud"])
    return df

df = cargar_credito()
monto_total = df["monto_solicitado"].sum()
tasa_default = df["default_90d"].mean()

print(f"Solicitudes cargadas: {len(df):,}")
print(f"Monto total solicitado: ${monto_total:,.2f}")
print(f"Tasa de default a 90 días: {tasa_default:.2%}")
"""},

{"type": "markdown", "source": r"""
## 2. Estructuras de datos idiomáticas

Antes de tocar pandas, vale la pena dominar las estructuras nativas: son más
rápidas para operaciones puntuales y evitan el overhead de crear un DataFrame
para algo trivial.

- **Comprehensions** (list/dict/set) en vez de loops con `.append()`.
- **`dataclasses`** para representar registros/config en vez de diccionarios sueltos.
- **`collections.Counter` / `defaultdict`** para conteos y agrupaciones rápidas.
"""},

{"type": "code", "source": r"""
from collections import Counter

# Comprehension con condición: sectores de solicitudes con monto > 500k
sectores_alto_monto = {row.sector for row in df.itertuples() if row.monto_solicitado > 500_000}
print("Sectores con solicitudes > $500k:", sectores_alto_monto)

# Counter para distribución rápida sin usar value_counts()
conteo_sectores = Counter(df["sector"])
print("\nTop 3 sectores por volumen de solicitudes:")
for sector, n in conteo_sectores.most_common(3):
    print(f"  {sector:<15} {n:>5,} solicitudes")
"""},

{"type": "code", "source": r"""
@dataclass(frozen=True)
class ReglaRiesgo:
    '''Regla de negocio para pre-aprobación automática.'''
    nombre: str
    score_minimo: int
    dti_maximo: float
    monto_maximo: float = field(default=1_000_000)

    def evalua(self, buro_score: float, dti: float, monto: float) -> bool:
        if pd.isna(buro_score):
            return False
        return buro_score >= self.score_minimo and dti <= self.dti_maximo and monto <= self.monto_maximo

regla_conservadora = ReglaRiesgo(nombre="conservadora", score_minimo=680, dti_maximo=0.35)

df["dti"] = df["deuda_actual"] / (df["ingreso_mensual"] + 1)
df["preaprobada"] = df.apply(
    lambda r: regla_conservadora.evalua(r["buro_score"], r["dti"], r["monto_solicitado"]), axis=1
)
print(f"Tasa de pre-aprobación con regla '{regla_conservadora.nombre}': {df['preaprobada'].mean():.2%}")
"""},

{"type": "markdown", "source": r"""
> **Nota de performance:** `df.apply(..., axis=1)` es legible pero lento en
> datasets grandes (itera fila por fila en Python puro). Para reglas simples
> como esta, la versión vectorizada es 10-50x más rápida:
> ```python
> df["preaprobada"] = (
>     (df["buro_score"] >= 680) & (df["dti"] <= 0.35) & (df["monto_solicitado"] <= 1_000_000)
> ).fillna(False)
> ```
> Regla práctica: usa `.apply()` para prototipar la lógica, vectoriza antes de
> correrlo sobre >100k filas o en producción.
"""},

{"type": "markdown", "source": r"""
## 3. Lectura robusta de CSV / Excel / JSON

En la vida real los datos llegan sucios: encodings raros, separadores decimales
distintos, hojas de Excel con encabezados desplazados, JSON anidado. Un analista
senior nunca asume que `pd.read_csv(path)` a secas va a funcionar en producción.
"""},

{"type": "code", "source": r"""
# CSV: parámetros que resuelven el 90% de los problemas de encoding/formato
df_robusto = pd.read_csv(
    DATA_DIR / "credito_solicitudes.csv",
    parse_dates=["fecha_solicitud"],
    dtype={"solicitud_id": "string", "sector": "category"},  # category ahorra memoria en columnas repetitivas
    encoding="utf-8",
    na_values=["", "NA", "N/A", "null"],
)
print(df_robusto.dtypes)
print(f"\nMemoria con dtypes optimizados: {df_robusto.memory_usage(deep=True).sum() / 1024:.1f} KB")
print(f"Memoria con dtypes por defecto:  {pd.read_csv(DATA_DIR / 'credito_solicitudes.csv').memory_usage(deep=True).sum() / 1024:.1f} KB")
"""},

{"type": "code", "source": r"""
import json

# JSON anidado (típico de respuestas de API) -> tabla plana con json_normalize
respuesta_api_simulada = {
    "solicitudes": [
        {"id": "CR-900001", "cliente": {"nombre": "Comercial Reyes", "sector": "Comercio"}, "monto": 250000, "score": 710},
        {"id": "CR-900002", "cliente": {"nombre": "TechNova SA", "sector": "Tecnología"}, "monto": 480000, "score": 655},
    ]
}
df_json = pd.json_normalize(respuesta_api_simulada["solicitudes"], sep="_")
df_json
"""},

{"type": "markdown", "source": r"""
Para Excel, los puntos que suelen romper pipelines:
```python
# Especificar hoja + saltar filas de encabezado "decorativo"
df_excel = pd.read_excel("reporte.xlsx", sheet_name="Detalle", skiprows=2, engine="openpyxl")

# Leer TODAS las hojas de una vez -> dict {nombre_hoja: DataFrame}
hojas = pd.read_excel("reporte.xlsx", sheet_name=None)

# Escribir varias hojas manteniendo formato
with pd.ExcelWriter("salida.xlsx", engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Solicitudes", index=False)
```
"""},

{"type": "markdown", "source": r"""
## 4. Consumo de APIs REST con `requests`

Patrón estándar para traer datos externos (tipos de cambio, indicadores
económicos, CRMs): sesión reutilizable, timeout explícito, reintentos con
backoff y manejo de rate limits.
"""},

{"type": "code", "source": r"""
import time
from typing import Any

def get_con_reintentos(
    url: str,
    params: dict[str, Any] | None = None,
    max_intentos: int = 3,
    timeout: float = 5.0,
):
    '''GET con reintentos y backoff exponencial. Patrón base para ingestión desde APIs.'''
    import requests
    from requests.exceptions import RequestException

    for intento in range(1, max_intentos + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except RequestException as e:
            espera = 2 ** intento  # backoff exponencial: 2s, 4s, 8s...
            print(f"Intento {intento}/{max_intentos} falló ({e}); reintentando en {espera}s")
            if intento == max_intentos:
                raise
            time.sleep(espera)

# Ejemplo real: tipo de cambio USD/MXN público (Banxico usa API con token;
# aquí usamos un endpoint público sin auth para el ejemplo)
try:
    data = get_con_reintentos("https://api.frankfurter.app/latest", params={"from": "USD", "to": "MXN"})
    print(data)
except Exception as e:
    print(f"[Sin conexión de red en este entorno — comportamiento esperado en sandbox] {e}")
"""},

{"type": "markdown", "source": r"""
## 5. Manejo de errores y logging en pipelines de ingestión

`print()` no escala: no tiene niveles, no tiene timestamps, no se puede filtrar
en producción. El módulo `logging` es estándar y gratis.
"""},

{"type": "code", "source": r"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingesta_credito")

def cargar_con_validacion(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.error(f"Archivo no encontrado: {path}")
        raise FileNotFoundError(path)

    df = pd.read_csv(path, parse_dates=["fecha_solicitud"])
    logger.info(f"Cargadas {len(df):,} filas desde {path.name}")

    nulos = df.isna().sum()
    columnas_con_nulos = nulos[nulos > 0]
    if not columnas_con_nulos.empty:
        logger.warning(f"Columnas con nulos: {dict(columnas_con_nulos)}")

    duplicados = df.duplicated(subset="solicitud_id").sum()
    if duplicados > 0:
        logger.warning(f"{duplicados} solicitud_id duplicados detectados — se recomienda deduplicar")

    return df

df_validado = cargar_con_validacion(DATA_DIR / "credito_solicitudes.csv")
"""},

{"type": "markdown", "source": r"""
## Resumen y siguientes pasos

- Usa `pathlib`, type hints y `dataclasses` para código que se pueda mantener.
- Vectoriza en pandas antes de escalar a producción; `.apply(axis=1)` es solo
  para prototipar.
- Nunca confíes en que un archivo externo esté limpio: valida nulos, duplicados
  y tipos al cargar.
- `logging` en vez de `print` desde el día uno de cualquier script que se vaya
  a programar (cron, Airflow, etc.).

**Siguiente módulo:** `02_librerias_numpy_pandas.ipynb` — NumPy y Pandas a
nivel avanzado (vectorización, merges, pivots, performance).
"""},
]
