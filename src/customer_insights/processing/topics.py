"""Traduce señales de texto/calificacion a categorias que el negocio entiende.

Este modulo es el corazon del enfoque "translator": convierte tokens de NLP
en temas de negocio accionables (tecnologia, atencion, costos, seguridad,
tiempos) y convierte calificaciones numericas en un lenguaje tipo NPS
(Promotor / Pasivo / Detractor) independientemente de si la escala original
es de 1 a 5 estrellas o de 0 a 10.
"""
from __future__ import annotations

from .clean import tokenizar

TEMAS_NEGOCIO: dict[str, set[str]] = {
    "Tecnologia / App": {
        "app", "aplicacion", "sistema", "actualizacion", "error", "errores", "falla",
        "fallas", "fallo", "lenta", "lento", "carga", "cae", "congela", "traba",
        "diseno", "version", "clave", "contrasena", "login", "plataforma",
    },
    "Atencion al cliente": {
        "atencion", "asesor", "asesora", "agente", "servicio", "trato", "amable",
        "grosero", "grosera", "prepotente", "chat", "respuesta", "responde",
        "sucursal", "personal", "call", "center",
    },
    "Costos y comisiones": {
        "comision", "comisiones", "cobro", "cobraron", "costo", "costos", "tarifa",
        "tarifas", "cargo", "cargos", "interes", "intereses", "mantenimiento",
        "abuso", "abusivo", "oculto", "ocultos",
    },
    "Seguridad": {
        "seguridad", "fraude", "estafa", "robo", "hackeo", "clave", "contrasena",
        "bloquearon", "bloqueado", "bloqueada", "autenticacion", "verificacion",
        "biometrica",
    },
    "Tiempos de espera": {
        "demora", "demoras", "demoro", "espera", "esperando", "tiempo", "tiempos",
        "rapido", "rapida", "lento", "lenta", "tardanza", "tardo", "tardaron",
    },
    "Transacciones": {
        "transferencia", "transferencias", "pago", "pagos", "retiro", "retiros",
        "deposito", "depositos", "tarjeta", "tarjetas", "cuenta", "saldo",
    },
}

TEMA_SIN_CLASIFICAR = "Otros / sin clasificar"


def etiquetar_tema_negocio(comentario: str) -> list[str]:
    """Devuelve la(s) categoria(s) de negocio detectadas en un comentario (puede ser mas de una)."""
    tokens = set(tokenizar(comentario, quitar_stopwords=False))
    temas = [tema for tema, palabras_clave in TEMAS_NEGOCIO.items() if tokens & palabras_clave]
    return temas or [TEMA_SIN_CLASIFICAR]


def etiquetar_categoria_nps(calificacion: float, escala_maxima: float = 5) -> str:
    """Traduce una calificacion numerica a una categoria tipo NPS.

    Con escala 1-5 (estrellas): 4-5 -> Promotor, 3 -> Pasivo, 1-2 -> Detractor.
    Con escala 0-10 (NPS clasico): 9-10 -> Promotor, 7-8 -> Pasivo, 0-6 -> Detractor.
    """
    if calificacion is None:
        return "Sin dato"

    if escala_maxima <= 5:
        if calificacion >= 4:
            return "Promotor"
        if calificacion >= 3:
            return "Pasivo"
        return "Detractor"

    # escala 0-10
    if calificacion >= 9:
        return "Promotor"
    if calificacion >= 7:
        return "Pasivo"
    return "Detractor"
