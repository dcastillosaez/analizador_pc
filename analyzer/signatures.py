"""Verificación de firma Authenticode de ejecutables.

La detección por entropía y por ruta se equivoca con facilidad en los dos
sentidos: un instalador legítimo comprimido parece aleatorio, y un binario
malicioso puede llamarse `update.exe` y vivir en una carpeta normal. Quién
firma el archivo es una señal mucho más limpia, y Windows ya la tiene.

Todas las rutas se comprueban en una sola llamada a PowerShell: hacerlo de una
en una serían decenas de arranques del shell.
"""

from ._shell import run_ps_json

# Editores cuyos binarios no hace falta mirar dos veces.
TRUSTED_PUBLISHERS = (
    "microsoft corporation",
    "microsoft windows",
    "microsoft windows hardware compatibility publisher",
)

# Comprobar más de esto en una sola llamada empieza a tardar de más.
MAX_BATCH = 60

_cache: dict[str, dict] = {}


def _script(paths: list[str]) -> str:
    # Las rutas van en un array literal; PowerShell las recibe ya escapadas
    # porque _shell las envía codificadas y el shell no reinterpreta nada.
    listado = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    return (
        f"@({listado}) | ForEach-Object {{"
        "  $p = $_;"
        "  try {"
        "    $s = Get-AuthenticodeSignature -LiteralPath $p -ErrorAction Stop;"
        "    [PSCustomObject]@{"
        "      Path = $p;"
        "      Status = $s.Status.ToString();"
        "      Signer = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }"
        "    }"
        "  } catch {"
        "    [PSCustomObject]@{ Path = $p; Status = 'Error'; Signer = '' }"
        "  }"
        "} | ConvertTo-Json -Compress -Depth 3"
    )


def _common_name(subject: str) -> str:
    """Saca el CN= del subject del certificado; ahí está el nombre del editor."""
    for part in (subject or "").split(","):
        part = part.strip()
        if part.upper().startswith("CN="):
            return part[3:].strip().strip('"')
    return (subject or "").strip()


def check_signatures(paths: list[str]) -> dict[str, dict]:
    """Devuelve {ruta_en_minúsculas: {status, signer, trusted}}.

    `status` es el de Windows: Valid, NotSigned, HashMismatch, UnknownError…
    Nunca lanza: si PowerShell falla, se devuelve lo que haya en caché.
    """
    unicas, pendientes = [], []
    for p in paths:
        if not p:
            continue
        clave = p.lower()
        if clave in _cache or clave in unicas:
            continue
        unicas.append(clave)
        pendientes.append(p)

    for i in range(0, len(pendientes), MAX_BATCH):
        lote = pendientes[i:i + MAX_BATCH]
        datos = run_ps_json(_script(lote), timeout=45, default=[]) or []
        if isinstance(datos, dict):
            datos = [datos]

        vistos = set()
        for fila in datos:
            if not isinstance(fila, dict):
                continue
            ruta = (fila.get("Path") or "").lower()
            if not ruta:
                continue
            firmante = _common_name(fila.get("Signer") or "")
            estado = fila.get("Status") or "Unknown"
            _cache[ruta] = {
                "status": estado,
                "signer": firmante,
                "trusted": estado == "Valid" and firmante.lower().startswith(TRUSTED_PUBLISHERS),
                "signed": estado == "Valid",
            }
            vistos.add(ruta)

        # Si PowerShell no devolvió nada para alguna ruta, se marca como
        # desconocida para no volver a preguntar por ella en este escaneo.
        for p in lote:
            if p.lower() not in vistos:
                _cache[p.lower()] = {"status": "Unknown", "signer": "",
                                     "trusted": False, "signed": False}

    return {p: _cache[p] for p in unicas if p in _cache}


def describe(info: dict) -> str:
    """Frase legible para la UI a partir del resultado de la comprobación."""
    if not info:
        return "No se pudo comprobar la firma digital."
    estado, firmante = info.get("status"), info.get("signer")
    if estado == "Valid":
        return f"Firmado por {firmante}." if firmante else "Tiene una firma digital válida."
    if estado == "NotSigned":
        return "No tiene firma digital."
    if estado == "HashMismatch":
        return "La firma no coincide con el contenido del archivo: ha sido modificado."
    if estado == "UnknownError":
        return "Tiene firma, pero este equipo no puede validar quién la emitió."
    if estado == "Error":
        return "No se pudo leer el archivo para comprobar su firma."
    return f"Estado de la firma: {estado}."
