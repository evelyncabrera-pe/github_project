CELLS = [
{"type": "markdown", "source": r"""
# 03 · SQL y bases de datos para análisis de datos

Un analista senior necesita moverse con soltura entre SQL y pandas: SQL para
extraer/agregar en la fuente (evita mover millones de filas a Python
innecesariamente), pandas para lo que SQL hace mal (transformaciones
iterativas, modelado, gráficas).

Usamos **SQLite** vía `sqlite3` (estándar de la librería, cero setup) para que
el notebook sea 100% autocontenido — la sintaxis SQL es prácticamente
idéntica en Postgres/MySQL/Snowflake salvo funciones específicas de fecha o
window functions avanzadas.

## Contenido
1. Crear una base de datos desde DataFrames existentes
2. `SELECT`, `WHERE`, `GROUP BY`, `HAVING` — lo esencial bien hecho
3. `JOIN`s: INNER vs LEFT, y el error clásico del "fan-out"
4. Window functions: `RANK`, `ROW_NUMBER`, running totals
5. `pandas.read_sql` vs. SQLAlchemy: cuándo usar cada uno
6. CTEs (`WITH`) para queries legibles en vez de subqueries anidadas
"""},

{"type": "code", "source": r"""
import sqlite3
import pandas as pd

pd.set_option("display.width", 120)

df_credito = pd.read_csv("data/credito_solicitudes.csv", parse_dates=["fecha_solicitud"])
df_ventas = pd.read_csv("data/ventas_ecommerce_tech.csv", parse_dates=["fecha"])

conn = sqlite3.connect(":memory:")  # base de datos en memoria, se pierde al cerrar la conexión
df_credito.to_sql("solicitudes", conn, index=False, if_exists="replace")
df_ventas.to_sql("ventas", conn, index=False, if_exists="replace")

print("Tablas creadas:", pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)["name"].tolist())
"""},

{"type": "markdown", "source": r"""
## 2. `SELECT` / `WHERE` / `GROUP BY` / `HAVING`

Regla clave de orden lógico de ejecución en SQL (no el orden que escribes):
`FROM` → `WHERE` → `GROUP BY` → `HAVING` → `SELECT` → `ORDER BY`. Por eso
`HAVING` filtra sobre agregados y `WHERE` no puede usar un alias definido en
`SELECT`.
"""},

{"type": "code", "source": r"""
query = '''
SELECT
    sector,
    COUNT(*)                                   AS n_solicitudes,
    ROUND(AVG(monto_solicitado), 2)            AS monto_promedio,
    ROUND(AVG(default_90d) * 100, 1)           AS tasa_default_pct
FROM solicitudes
WHERE buro_score IS NOT NULL
GROUP BY sector
HAVING COUNT(*) > 100
ORDER BY tasa_default_pct DESC
'''
pd.read_sql(query, conn)
"""},

{"type": "markdown", "source": r"""
## 3. JOINs: INNER vs LEFT, y el "fan-out"

**Fan-out**: cuando la tabla de la derecha tiene múltiples filas por llave de
la izquierda, el join multiplica filas de la izquierda. Es la causa #1 de
"mis totales no cuadran" en reportes con SQL.
"""},

{"type": "code", "source": r"""
# Tabla resumen por sector (1 fila por sector) -> join seguro, no hay fan-out
query_left_seguro = '''
SELECT
    s.solicitud_id,
    s.sector,
    s.monto_solicitado,
    r.tasa_default_sector
FROM solicitudes s
LEFT JOIN (
    SELECT sector, ROUND(AVG(default_90d), 3) AS tasa_default_sector
    FROM solicitudes
    GROUP BY sector
) r ON s.sector = r.sector
LIMIT 5
'''
print("Filas originales:", pd.read_sql("SELECT COUNT(*) AS n FROM solicitudes", conn)["n"][0])
print("Filas tras LEFT JOIN 1:1 por sector:",
      pd.read_sql(query_left_seguro.replace("LIMIT 5", ""), conn).shape[0])
pd.read_sql(query_left_seguro, conn)
"""},

{"type": "markdown", "source": r"""
## 4. Window functions

A diferencia de `GROUP BY` (que colapsa filas), las window functions calculan
un agregado **sin perder el detalle por fila** — perfectas para rankings,
"top N por grupo" y totales acumulados.
"""},

{"type": "code", "source": r"""
query_ranking = '''
SELECT
    sector,
    solicitud_id,
    monto_solicitado,
    RANK() OVER (PARTITION BY sector ORDER BY monto_solicitado DESC) AS ranking_en_sector
FROM solicitudes
QUALIFY ranking_en_sector <= 2
'''
# SQLite no soporta QUALIFY (sí Postgres/Snowflake/BigQuery) -> se envuelve en subquery
query_ranking_sqlite = '''
SELECT * FROM (
    SELECT
        sector,
        solicitud_id,
        monto_solicitado,
        RANK() OVER (PARTITION BY sector ORDER BY monto_solicitado DESC) AS ranking_en_sector
    FROM solicitudes
)
WHERE ranking_en_sector <= 2
ORDER BY sector, ranking_en_sector
'''
pd.read_sql(query_ranking_sqlite, conn)
"""},

{"type": "code", "source": r"""
# Running total: ingresos acumulados por categoría a lo largo del tiempo
query_running_total = '''
SELECT
    fecha,
    categoria,
    SUM(ingresos) AS ingresos_dia,
    SUM(SUM(ingresos)) OVER (
        PARTITION BY categoria ORDER BY fecha
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS ingresos_acumulados
FROM ventas
WHERE categoria = 'Laptops'
GROUP BY fecha, categoria
ORDER BY fecha
LIMIT 5
'''
pd.read_sql(query_running_total, conn)
"""},

{"type": "markdown", "source": r"""
## 5. `pandas.read_sql` vs. SQLAlchemy

- **`sqlite3`/`psycopg2` + `pd.read_sql`**: rápido para exploración, scripts
  puntuales, notebooks.
- **SQLAlchemy**: capa de abstracción — necesaria cuando el pipeline debe
  funcionar contra múltiples motores (dev en SQLite, prod en Postgres), o
  cuando se necesita un pool de conexiones y manejo transaccional serio.

```python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://usuario:password@host:5432/db")

# Parámetros bind -> SIEMPRE así con inputs externos, nunca f-strings (SQL injection)
query = text("SELECT * FROM solicitudes WHERE sector = :sector AND monto_solicitado > :monto_min")
df = pd.read_sql(query, engine, params={"sector": "Tecnología", "monto_min": 200_000})
```
"""},

{"type": "code", "source": r"""
# Ejemplo de por qué los parámetros bind importan: nunca construir SQL con f-strings sobre input externo
sector_input = "Tecnología"  # imagina que esto viene de un formulario/API

# MAL (vulnerable a SQL injection si sector_input viniera de un usuario):
# query_malo = f"SELECT * FROM solicitudes WHERE sector = '{sector_input}'"

# BIEN: placeholders con sqlite3 (?) o SQLAlchemy (:nombre)
query_seguro = "SELECT COUNT(*) AS n FROM solicitudes WHERE sector = ?"
pd.read_sql(query_seguro, conn, params=(sector_input,))
"""},

{"type": "markdown", "source": r"""
## 6. CTEs (`WITH`) para queries legibles

Las Common Table Expressions evitan anidar subqueries ilegibles: se leen de
arriba a abajo, como pasos de un pipeline.
"""},

{"type": "code", "source": r"""
query_cte = '''
WITH resumen_sector AS (
    SELECT
        sector,
        AVG(buro_score)     AS score_promedio,
        AVG(default_90d)    AS tasa_default
    FROM solicitudes
    WHERE buro_score IS NOT NULL
    GROUP BY sector
),
sectores_riesgo_alto AS (
    SELECT sector
    FROM resumen_sector
    WHERE tasa_default > (SELECT AVG(tasa_default) FROM resumen_sector)
)
SELECT
    s.solicitud_id,
    s.sector,
    s.monto_solicitado,
    s.buro_score
FROM solicitudes s
INNER JOIN sectores_riesgo_alto sra ON s.sector = sra.sector
WHERE s.buro_score < 500
ORDER BY s.monto_solicitado DESC
LIMIT 5
'''
pd.read_sql(query_cte, conn)
"""},

{"type": "code", "source": r"""
conn.close()
"""},

{"type": "markdown", "source": r"""
## Resumen y siguientes pasos

- Empuja agregaciones y filtros a SQL cuando la fuente es una base de
  datos — es más rápido que traer todo a pandas y filtrar ahí.
- Cuidado con el fan-out en JOINs: valida que el conteo de filas post-join
  sea el esperado.
- Window functions (`RANK`, `SUM() OVER`) resuelven "top N por grupo" y
  acumulados sin perder el detalle de fila.
- Nunca construyas SQL con f-strings sobre input externo — usa parámetros
  bind siempre.
- CTEs (`WITH`) en vez de subqueries anidadas para queries mantenibles.

**Siguiente módulo:** `04_estadistica_aplicada.ipynb` — estadística para
decisiones de negocio, no solo teoría.
"""},
]
