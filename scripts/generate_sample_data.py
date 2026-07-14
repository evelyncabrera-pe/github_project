"""Genera un dataset sintetico de opiniones de clientes de banca digital en espanol.

Este script NO reemplaza datos reales: sirve para que el pipeline y el dashboard
funcionen de extremo a extremo sin depender de conexion a internet ni de scraping
en vivo. El dataset resultante se guarda en data/sample/resenas_banca_muestra.csv
y queda versionado en el repositorio para que cualquiera pueda clonar y ejecutar
el proyecto sin pasos adicionales.

Para datos reales, usar el conector de Play Store (src/customer_insights/ingestion/play_store.py)
o el cargador de CSV (csv_loader.py) apuntando a un dataset publico propio.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

BANCOS = ["BBVA", "Santander", "BCP", "Interbank", "Banco de Chile", "Nubank", "Banorte", "Scotiabank"]
CANALES = ["App Movil", "Banca en Linea", "Chat / Call Center", "App Movil", "App Movil", "Banca en Linea"]

# Plantillas por sentimiento y tema de negocio. {banco} se reemplaza al generar.
PLANTILLAS = {
    "positivo": {
        "tecnologia": [
            "La app de {banco} es muy rapida y facil de usar, hago todo en segundos.",
            "Excelente experiencia con la aplicacion de {banco}, nunca habia sido tan simple.",
            "Me encanta el nuevo diseno de la app, es intuitivo y no se traba.",
            "La actualizacion de la app quedo genial, ahora todo carga mas rapido.",
            "Muy buena la app movil, puedo hacer transferencias sin ningun problema.",
        ],
        "atencion": [
            "El asesor de {banco} fue muy amable y resolvio mi duda al instante.",
            "Excelente atencion por chat, me ayudaron rapido y con mucha paciencia.",
            "El servicio al cliente de {banco} superó mis expectativas, muy atentos.",
            "Muy buena atencion en la sucursal, todo el personal fue amable.",
        ],
        "costos": [
            "No cobran comision por transferencias, muy conveniente usar {banco}.",
            "Me gusta que {banco} no tiene cargos ocultos, todo es transparente.",
            "Las tarifas de {banco} son las mas bajas que he encontrado.",
        ],
        "seguridad": [
            "Me siento muy segura con la autenticacion de dos pasos de {banco}.",
            "La app tiene buena seguridad, siempre piden verificacion biometrica.",
            "Nunca he tenido problemas de seguridad con {banco}, confio plenamente.",
        ],
        "tiempos": [
            "Todo fue muy rapido, en minutos ya tenia mi tarjeta activada.",
            "El tramite en {banco} fue rapidisimo, no esperé nada.",
            "Aprobaron mi solicitud en menos de un dia, excelente tiempo de respuesta.",
        ],
    },
    "neutral": {
        "tecnologia": [
            "La app de {banco} funciona bien pero podria mejorar el diseno.",
            "Cumple con lo basico, aunque le faltan algunas funciones utiles.",
            "La aplicacion esta bien pero a veces tarda un poco en cargar.",
        ],
        "atencion": [
            "La atencion fue normal, ni buena ni mala, resolvieron mi caso.",
            "El asesor fue correcto pero se demoro un poco en responder.",
        ],
        "costos": [
            "Las comisiones de {banco} son similares a las de otros bancos.",
            "El costo del mantenimiento de cuenta esta en el promedio del mercado.",
        ],
        "tiempos": [
            "El tramite tomo el tiempo esperado, sin sorpresas.",
            "La atencion en sucursal fue en un tiempo razonable.",
        ],
    },
    "negativo": {
        "tecnologia": [
            "La app de {banco} se cae constantemente y no puedo revisar mi saldo.",
            "Pesima actualizacion, ahora la aplicacion es mas lenta que antes.",
            "Llevo dias intentando entrar a la app y siempre marca error.",
            "La app se congela cada vez que intento hacer una transferencia.",
            "Muy mala experiencia, la aplicacion de {banco} no carga nunca.",
        ],
        "atencion": [
            "El asesor de {banco} fue muy grosero y no resolvio mi problema.",
            "Pesimo servicio al cliente, nadie responde en el chat.",
            "Me tuvieron horas en espera y al final no solucionaron nada.",
            "Muy mala atencion en la sucursal, el personal fue prepotente.",
        ],
        "costos": [
            "Me cobraron una comision que nadie me explico, pesimo servicio.",
            "Los cargos ocultos de {banco} son un abuso total.",
            "Subieron la comision de mantenimiento sin avisarme, muy molesto.",
        ],
        "seguridad": [
            "Sufri un intento de fraude y el banco tardo dias en responder.",
            "Me bloquearon la cuenta sin explicacion y fue una pesadilla recuperarla.",
            "Tengo miedo de usar la app de {banco}, no confio en su seguridad.",
        ],
        "tiempos": [
            "Llevo mas de una hora esperando que me atiendan en el chat.",
            "El tramite de mi tarjeta demoro casi un mes, una demora inaceptable.",
            "Demasiada demora para resolver un reclamo simple, muy mala experiencia.",
        ],
    },
}

RATING_POR_SENTIMIENTO = {
    "positivo": [4, 5, 5],
    "neutral": [3],
    "negativo": [1, 1, 2],
}


def generar_filas(n: int) -> list[dict]:
    filas = []
    hoy = date.today()
    for i in range(1, n + 1):
        sentimiento = random.choices(
            population=["positivo", "neutral", "negativo"],
            weights=[0.40, 0.15, 0.45],
            k=1,
        )[0]
        tema = random.choice(list(PLANTILLAS[sentimiento].keys()))
        plantilla = random.choice(PLANTILLAS[sentimiento][tema])
        banco = random.choice(BANCOS)
        comentario = plantilla.format(banco=banco)
        rating = random.choice(RATING_POR_SENTIMIENTO[sentimiento])
        dias_atras = random.randint(0, 365)
        fecha = hoy - timedelta(days=dias_atras)
        canal = random.choice(CANALES)
        filas.append(
            {
                "id_resena": i,
                "banco": banco,
                "canal": canal,
                "fecha": fecha.isoformat(),
                "calificacion": rating,
                "comentario": comentario,
                "tema_sintetico": tema,  # solo para validar el dataset, no se usa en el pipeline
            }
        )
    return filas


def main() -> None:
    salida = Path(__file__).resolve().parent.parent / "data" / "sample" / "resenas_banca_muestra.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    filas = generar_filas(320)
    with salida.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    print(f"Generadas {len(filas)} filas en {salida}")


if __name__ == "__main__":
    main()
