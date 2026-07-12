"""
Genera los datasets sintéticos usados en todos los notebooks del curso.

Se generan de forma programática (con seed fija) para que:
  - No dependan de descargas externas (reproducibles offline).
  - Tengan patrones realistas (correlaciones, estacionalidad, ruido)
    sobre los que valga la pena aplicar EDA / estadística / ML.

Ejecutar una sola vez:
    python data/generate_datasets.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
OUT = Path(__file__).parent


def generar_credito(n=6000) -> pd.DataFrame:
    """Solicitudes de crédito estilo fintech (KapitalFlex-like)."""
    edad = RNG.normal(38, 11, n).clip(18, 75).round().astype(int)
    antiguedad_laboral = (edad - RNG.integers(18, 25, n)).clip(0, None)
    ingreso_mensual = RNG.lognormal(mean=8.2, sigma=0.55, size=n).round(2)  # MXN
    sector = RNG.choice(
        ["Comercio", "Manufactura", "Servicios", "Tecnología", "Construcción", "Agro"],
        size=n, p=[0.28, 0.18, 0.24, 0.12, 0.1, 0.08],
    )
    antiguedad_empresa = RNG.gamma(shape=2.2, scale=3.5, size=n).clip(0, 40).round(1)
    num_creditos_previos = RNG.poisson(1.4, n)
    deuda_actual = (ingreso_mensual * RNG.uniform(0, 4, n) * (num_creditos_previos > 0)).round(2)

    buro_score = (
        650
        + (ingreso_mensual / ingreso_mensual.mean() - 1) * 60
        - (deuda_actual / (ingreso_mensual + 1)) * 90
        + antiguedad_empresa * 1.8
        + RNG.normal(0, 45, n)
    ).clip(300, 850).round().astype(int)

    monto_solicitado = (ingreso_mensual * RNG.uniform(1.5, 8, n)).round(2)
    plazo_meses = RNG.choice([6, 12, 18, 24, 36, 48], size=n, p=[0.15, 0.25, 0.2, 0.2, 0.12, 0.08])
    tasa_interes = (0.28 - (buro_score - 300) / 550 * 0.16 + RNG.normal(0, 0.015, n)).clip(0.09, 0.35).round(4)

    dti = deuda_actual / (ingreso_mensual + 1)  # debt-to-income
    score_z = (buro_score - 650) / 100
    monto_ratio = monto_solicitado / ingreso_mensual
    logit = (
        -6.5
        + 1.1 * dti
        - 0.9 * score_z
        + 0.15 * monto_ratio
        - 0.02 * antiguedad_empresa
        + RNG.normal(0, 0.4, n)
    )
    prob_default = 1 / (1 + np.exp(-logit))
    default_flag = (RNG.uniform(0, 1, n) < prob_default).astype(int)

    fecha_solicitud = pd.to_datetime("2023-01-01") + pd.to_timedelta(
        RNG.integers(0, 900, n), unit="D"
    )

    df = pd.DataFrame({
        "solicitud_id": [f"CR-{100000+i}" for i in range(n)],
        "fecha_solicitud": fecha_solicitud,
        "edad": edad,
        "sector": sector,
        "antiguedad_laboral_anios": antiguedad_laboral,
        "antiguedad_empresa_anios": antiguedad_empresa,
        "ingreso_mensual": ingreso_mensual,
        "deuda_actual": deuda_actual,
        "num_creditos_previos": num_creditos_previos,
        "buro_score": buro_score,
        "monto_solicitado": monto_solicitado,
        "plazo_meses": plazo_meses,
        "tasa_interes": tasa_interes,
        "default_90d": default_flag,
    })

    # Nulos e inconsistencias intencionales para practicar limpieza en EDA
    idx_nulos = RNG.choice(n, size=int(n * 0.04), replace=False)
    df.loc[idx_nulos, "ingreso_mensual"] = np.nan
    idx_nulos2 = RNG.choice(n, size=int(n * 0.02), replace=False)
    df.loc[idx_nulos2, "buro_score"] = np.nan
    idx_dup = RNG.choice(n, size=15, replace=False)
    df = pd.concat([df, df.loc[idx_dup]], ignore_index=True)

    return df.sample(frac=1, random_state=1).reset_index(drop=True)


def generar_ventas_ecommerce(n_dias=730) -> pd.DataFrame:
    """Ventas diarias de un marketplace de electrónica/tech (multi-categoría, multi-región)."""
    fechas = pd.date_range("2023-01-01", periods=n_dias, freq="D")
    categorias = {
        "Laptops": (1400, 0.25),
        "Smartphones": (900, 0.35),
        "Audio": (180, 0.5),
        "Accesorios": (45, 0.7),
        "Gaming": (650, 0.3),
    }
    regiones = ["Norte", "Centro", "Sur", "Bajío"]

    filas = []
    for cat, (precio_base, elasticidad) in categorias.items():
        tendencia = np.linspace(1.0, RNG.uniform(1.15, 1.6), n_dias)
        estacionalidad_semanal = 1 + 0.18 * np.sin(2 * np.pi * np.arange(n_dias) / 7 + RNG.uniform(0, 1))
        dia_del_anio = fechas.dayofyear.to_numpy()
        estacionalidad_anual = 1 + 0.35 * np.sin(2 * np.pi * (dia_del_anio + RNG.integers(0, 60)) / 365)
        # Pico de fin de año (Buen Fin / Navidad)
        pico_bf = np.where((fechas.month == 11) & (fechas.day >= 15), 1.8, 1.0)
        pico_navidad = np.where((fechas.month == 12) & (fechas.day <= 24), 1.5, 1.0)
        ruido = RNG.normal(1, 0.12, n_dias)

        unidades = (
            25 * tendencia * estacionalidad_semanal * estacionalidad_anual * pico_bf * pico_navidad * ruido
        ).clip(0, None)

        for region in regiones:
            factor_region = RNG.uniform(0.6, 1.3)
            unidades_region = (unidades * factor_region * RNG.uniform(0.85, 1.15, n_dias)).round().astype(int)
            precio_promedio = (precio_base * RNG.normal(1, 0.05, n_dias)).clip(precio_base * 0.6, None).round(2)
            filas.append(pd.DataFrame({
                "fecha": fechas,
                "categoria": cat,
                "region": region,
                "unidades_vendidas": unidades_region,
                "precio_promedio": precio_promedio,
                "ingresos": (unidades_region * precio_promedio).round(2),
            }))

    df = pd.concat(filas, ignore_index=True)
    return df


def generar_precios_acciones_tech(n_dias=1000) -> pd.DataFrame:
    """Series de tiempo sintéticas estilo acciones tech (para forecasting)."""
    fechas = pd.bdate_range("2021-01-04", periods=n_dias)
    tickers = {
        "TCH": (150, 0.018, 0.0006),
        "NEX": (80, 0.024, 0.0004),
        "DTA": (300, 0.015, 0.0008),
    }
    filas = []
    for ticker, (precio_inicial, vol, drift) in tickers.items():
        retornos = RNG.normal(drift, vol, n_dias)
        precio = precio_inicial * np.exp(np.cumsum(retornos))
        volumen = (RNG.lognormal(13, 0.4, n_dias)).round().astype(int)
        filas.append(pd.DataFrame({
            "fecha": fechas,
            "ticker": ticker,
            "precio_cierre": precio.round(2),
            "volumen": volumen,
        }))
    return pd.concat(filas, ignore_index=True)


if __name__ == "__main__":
    df_credito = generar_credito()
    df_credito.to_csv(OUT / "credito_solicitudes.csv", index=False)
    print(f"credito_solicitudes.csv -> {df_credito.shape}")

    df_ventas = generar_ventas_ecommerce()
    df_ventas.to_csv(OUT / "ventas_ecommerce_tech.csv", index=False)
    print(f"ventas_ecommerce_tech.csv -> {df_ventas.shape}")

    df_acciones = generar_precios_acciones_tech()
    df_acciones.to_csv(OUT / "precios_acciones_tech.csv", index=False)
    print(f"precios_acciones_tech.csv -> {df_acciones.shape}")
