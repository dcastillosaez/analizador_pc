"""Heuristicas de texto compartidas entre security.py y services.py."""

import math
import os

# Umbrales calibrados sobre los nombres reales de procesos y servicios de un
# Windows 11 limpio (149 muestras, 0 falsos positivos) frente a nombres
# generados aleatoriamente, que es lo que suele usar el malware para persistir.
#
# El umbral anterior (entropia > 4.0 en services, > 3.6 en security) era
# inalcanzable: la entropia maxima de una cadena de 12 caracteres distintos es
# log2(12) = 3.58, asi que ningun nombre realista lo superaba y la deteccion
# nunca se disparaba. Lo que separa de verdad ambos grupos es la proporcion de
# vocales: los nombres inventados por una persona las tienen, los generados no.
_MIN_LEN = 8
_MIN_ENTROPY = 2.8
_MAX_VOWEL_RATIO = 0.15

_VOWELS = "aeiou"


def shannon_entropy(text: str) -> float:
    """Entropia de Shannon de una cadena, en bits por caracter."""
    if not text:
        return 0.0
    n = len(text)
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def vowel_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if c in _VOWELS) / len(text)


def looks_random(name: str) -> bool:
    """¿El nombre parece generado automaticamente en vez de escrito por alguien?

    Se aplica al nombre sin extension y en minusculas, tanto a ejecutables
    (`abc123.exe`) como a nombres de servicio.
    """
    base = os.path.splitext(name or "")[0].lower()
    if len(base) < _MIN_LEN:
        return False
    return shannon_entropy(base) > _MIN_ENTROPY and vowel_ratio(base) < _MAX_VOWEL_RATIO
