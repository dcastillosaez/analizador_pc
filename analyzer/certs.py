"""
Certificados del sistema — almacén de Windows.
Detecta certificados caducados o próximos a caducar.
"""
import json
from datetime import datetime, timezone

from ._shell import run_ps, run_ps_json


_PS = r"""
$stores = @(
  @{Path='Cert:\LocalMachine\My';    Name='Equipo · Personal'},
  @{Path='Cert:\LocalMachine\Root';  Name='Equipo · Entidades raíz de confianza'},
  @{Path='Cert:\LocalMachine\CA';    Name='Equipo · Entidades emisoras intermedias'},
  @{Path='Cert:\CurrentUser\My';     Name='Usuario · Personal'}
)
$result = @()
foreach ($s in $stores) {
  try {
    Get-ChildItem $s.Path -ErrorAction SilentlyContinue | ForEach-Object {
      $result += [PSCustomObject]@{
        Subject       = $_.Subject
        Issuer        = $_.Issuer
        NotBefore     = $_.NotBefore.ToString('o')
        NotAfter      = $_.NotAfter.ToString('o')
        Thumbprint    = $_.Thumbprint
        HasPrivateKey = $_.HasPrivateKey
        Store         = $s.Name
        StorePath     = $s.Path
        FriendlyName  = $_.FriendlyName
      }
    }
  } catch {}
}
$result | ConvertTo-Json -Compress -Depth 2
"""


def _common_name(subject: str) -> str:
    """Extrae CN= del Subject, o devuelve el subject completo si no hay CN."""
    for part in subject.split(","):
        p = part.strip()
        if p.upper().startswith("CN="):
            return p[3:].strip()
    return subject.strip()


def analyze_certs() -> dict:
    try:
        certs_raw = run_ps_json(_PS, timeout=30, default=[]) or []
    except Exception as exc:
        return {
            "status": "warning", "title": "Certificados del sistema",
            "summary": f"No se pudo consultar el almacén de certificados: {exc}",
            "issue_count": 0, "items": [],
        }

    now = datetime.now(timezone.utc)
    WARN_DAYS  = 90
    CRIT_DAYS  = 30

    items: list[dict] = []
    expired_n = warning_n = 0

    for cert in certs_raw:
        if not isinstance(cert, dict):
            continue
        subject  = cert.get("Subject", "") or ""
        issuer   = cert.get("Issuer",  "") or ""
        not_after_raw = cert.get("NotAfter", "")
        store    = cert.get("Store", "")
        friendly = cert.get("FriendlyName", "") or ""
        thumbprint = (cert.get("Thumbprint", "") or "")[:16] + "…"

        try:
            not_after = datetime.fromisoformat(not_after_raw)
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        days_left = (not_after - now).days
        cn    = _common_name(subject) or friendly or "(sin nombre)"
        cn_is = _common_name(issuer)

        if days_left < 0:
            status = "danger"
            msg    = f"Caducado hace {abs(days_left)} día(s)"
            expired_n += 1
        elif days_left <= CRIT_DAYS:
            status = "danger"
            msg    = f"Caduca en {days_left} día(s)"
            expired_n += 1
        elif days_left <= WARN_DAYS:
            status = "warning"
            msg    = f"Caduca en {days_left} día(s)"
            warning_n += 1
        else:
            continue  # OK — no añadir ítems de certificados sanos

    # Si no hay problemas, devolver resumen positivo sin items
    if not items and expired_n == 0 and warning_n == 0:
        # Reconstruir solo para el conteo total
        total = len(certs_raw)
        return {
            "status": "ok",
            "title":  "Certificados del sistema",
            "summary": f"{total} certificados analizados. Ninguno caducado ni próximo a caducar.",
            "issue_count": 0,
            "items": [],
            "total": total,
        }

    # Reconstruir items (necesitamos dos pasadas para tener expired_n antes)
    items = []
    expired_n = warning_n = 0
    for cert in certs_raw:
        if not isinstance(cert, dict):
            continue
        subject       = cert.get("Subject", "") or ""
        issuer        = cert.get("Issuer",  "") or ""
        not_after_raw = cert.get("NotAfter", "")
        store         = cert.get("Store", "")
        store_path    = cert.get("StorePath", "")
        friendly      = cert.get("FriendlyName", "") or ""
        thumbprint    = cert.get("Thumbprint", "") or ""

        try:
            not_after = datetime.fromisoformat(not_after_raw)
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        days_left = (not_after - now).days
        cn    = _common_name(subject) or friendly or "(sin nombre)"
        cn_is = _common_name(issuer)

        if days_left < 0:
            status = "danger"
            msg    = f"Caducado hace {abs(days_left)} día(s)"
            value  = "Caducado"
            expired_n += 1
        elif days_left <= CRIT_DAYS:
            status = "danger"
            msg    = f"Caduca en {days_left} día(s)"
            value  = f"{days_left}d"
            expired_n += 1
        elif days_left <= WARN_DAYS:
            status = "warning"
            msg    = f"Caduca en {days_left} día(s)"
            value  = f"{days_left}d"
            warning_n += 1
        else:
            continue

        items.append({
            "name":       cn,
            "status":     status,
            "message":    msg,
            "value":      value,
            "detail":     f"Emisor: {cn_is}  ·  Huella: {thumbprint[:20]}…",
            "expires":    not_after.strftime("%d/%m/%Y"),
            "store":      store,
            "store_path": store_path,
            "thumbprint": thumbprint,
            "can_delete": status == "danger",  # solo sugerir borrado en caducados
        })

    items.sort(key=lambda i: (0 if i["status"] == "danger" else 1, i["name"]))

    total = len(certs_raw)
    if expired_n:
        overall = "danger"
        summary = f"{expired_n} certificado(s) caducado(s) o a punto de caducar. Renuévalos para evitar errores de seguridad."
    else:
        overall = "warning"
        summary = f"{warning_n} certificado(s) caducarán en menos de {WARN_DAYS} días."

    return {
        "status":      overall,
        "title":       "Certificados del sistema",
        "summary":     summary,
        "issue_count": expired_n + warning_n,
        "items":       items,
        "total":       total,
    }


def delete_cert(store_path: str, thumbprint: str) -> dict:
    """Elimina un certificado del almacén de Windows por thumbprint. Requiere admin."""
    import re
    if not re.match(r'^Cert:[\\\/](LocalMachine|CurrentUser)[\\\/][\w]+$', store_path):
        return {"success": False, "message": "Ruta de almacén no válida."}
    if not re.match(r'^[0-9A-Fa-f]{40}$', thumbprint):
        return {"success": False, "message": "Huella digital no válida."}

    cmd = (
        f"$cert = Get-ChildItem '{store_path}' | Where-Object {{$_.Thumbprint -eq '{thumbprint}'}};"
        f"if ($cert) {{ $cert | Remove-Item -Force; Write-Output 'OK' }}"
        f"else {{ Write-Output 'NOT_FOUND' }}"
    )
    res = run_ps(cmd, timeout=20)
    out, err = res.stdout.strip(), res.stderr.strip()
    if "OK" in out:
        return {"success": True, "message": "Certificado eliminado correctamente."}
    if "NOT_FOUND" in out:
        return {"success": False, "message": "Certificado no encontrado en el almacén."}
    if res.needs_admin:
        return {"success": False, "message": "Se necesitan permisos de administrador. Reinicia PC Guardian como administrador."}
    return {"success": False, "message": err[:200] or res.error or "Error desconocido."}
