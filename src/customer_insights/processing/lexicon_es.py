"""Lexico de polaridad en español orientado a experiencia de cliente en banca digital.

Enfoque deliberadamente simple y transparente (tipo VADER): cada palabra tiene
un peso de polaridad, y se ajusta por negadores ("no", "nunca", "sin", "ni")
e intensificadores ("muy", "demasiado"). Es explicable palabra por palabra,
lo cual es valioso para comunicar resultados a negocio ("¿por que este
comentario se clasifico como negativo? por las palabras X, Y").

No pretende competir en precision con un modelo transformer (ver
processing/sentiment.py -> TransformerSentimentAnalyzer, backend opcional
basado en pysentimiento), pero no requiere descargar ningun modelo pesado.

Todas las entradas van sin tildes porque clean.limpiar_texto() las elimina
antes de tokenizar.
"""
from __future__ import annotations

PALABRAS_POSITIVAS: dict[str, float] = {
    "rapida": 1.0, "rapido": 1.0, "rapidos": 1.0, "rapidas": 1.0,
    "rapidisima": 1.5, "rapidisimo": 1.5,
    "facil": 1.0, "sencillo": 1.0, "sencilla": 1.0,
    "excelente": 2.0, "excelentes": 2.0,
    "simple": 0.8, "encanta": 1.5, "encantador": 1.2,
    "intuitivo": 1.0, "intuitiva": 1.0, "genial": 1.5,
    "buena": 1.0, "bueno": 1.0, "buenas": 1.0, "buenos": 1.0,
    "amable": 1.3, "amables": 1.3,
    "resolvio": 1.0, "resolvieron": 1.0, "resolver": 0.8, "resuelto": 1.0, "resuelve": 1.0,
    "soluciona": 0.8, "solucionaron": 1.0, "solucionar": 0.8,
    "supero": 1.3, "atentos": 1.2, "atenta": 1.2,
    "gusta": 1.0, "conveniente": 1.0, "transparente": 1.0,
    "segura": 1.0, "seguro": 1.0, "confio": 1.2, "confiable": 1.2,
    "activada": 0.5, "satisfecho": 1.5, "satisfecha": 1.5,
    "recomiendo": 1.5, "recomendable": 1.3,
    "perfecto": 1.8, "perfecta": 1.8,
    "comodo": 1.0, "comoda": 1.0, "eficiente": 1.2,
    "agradable": 1.0, "fluido": 1.0, "fluida": 1.0,
    "feliz": 1.5, "contento": 1.3, "contenta": 1.3,
    "exitoso": 1.0, "exitosa": 1.0,
}

PALABRAS_NEGATIVAS: dict[str, float] = {
    "lenta": 1.0, "lento": 1.0, "lentos": 1.0, "lentas": 1.0,
    "pesima": 2.0, "pesimo": 2.0, "pesimos": 2.0, "pesimas": 2.0,
    "error": 1.0, "errores": 1.0, "falla": 1.0, "fallas": 1.0, "fallo": 1.0,
    "cae": 1.0, "congela": 1.2, "traba": 1.0,
    "problema": 0.8, "problemas": 0.8,
    "grosero": 1.5, "grosera": 1.5, "groseros": 1.5,
    "nadie": 0.8, "prepotente": 1.5, "prepotentes": 1.5,
    "abuso": 1.5, "abusivo": 1.5, "abusiva": 1.5,
    "oculto": 1.0, "ocultos": 1.0, "oculta": 1.0, "ocultas": 1.0,
    "molesto": 1.2, "molesta": 1.2, "molestos": 1.2, "molestas": 1.2,
    "fraude": 2.0, "estafa": 2.0, "robo": 1.8, "hackeo": 1.8,
    "tardo": 0.8, "tardaron": 0.8,
    "bloquearon": 1.3, "bloqueado": 1.0, "bloqueada": 1.0,
    "pesadilla": 1.8, "miedo": 1.2,
    "inaceptable": 1.8,
    "mala": 1.2, "malo": 1.2, "malos": 1.2, "malas": 1.2,
    "demora": 0.8, "demoras": 0.8, "demoro": 0.8, "tardanza": 0.8,
    "espera": 0.6, "esperando": 0.6,
    "queja": 1.0, "quejas": 1.0, "reclamo": 0.8, "reclamos": 0.8,
    "decepcion": 1.5, "decepcionado": 1.5, "decepcionada": 1.5,
    "terrible": 1.8, "horrible": 1.8,
    "caotico": 1.3, "desastre": 1.8, "desastroso": 1.8,
}

NEGADORES: set[str] = {"no", "nunca", "sin", "ni", "tampoco", "jamas"}

INTENSIFICADORES: dict[str, float] = {
    "muy": 1.4, "demasiado": 1.6, "super": 1.5, "totalmente": 1.5,
    "sumamente": 1.6, "extremadamente": 1.7, "bastante": 1.2,
}

VENTANA_NEGACION = 3  # cuantos tokens despues de un negador pueden verse afectados
