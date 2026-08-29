"""Puntos de restauración del sistema.

Tres operaciones de la app tocan el sistema de forma difícil de deshacer:
desinstalar un controlador, instalar una actualización de Windows y eliminar un
certificado. Crear un punto de restauración antes cuesta unos segundos y cambia
por completo lo que pasa cuando algo sale mal.

Es best-effort a propósito: si la protección del sistema está apagada o falta
elevación, la operación sigue adelante y se avisa, en vez de bloquearla.
"""

from ._shell import run_ps, run_ps_json

# Windows limita la creación a un punto cada 24 h salvo que se ajuste esta
# clave. Se baja a 0 solo durante la llamada y se restaura después: dejarla a 0
# de forma permanente llenaría el disco de puntos.
_PS_CREATE = r"""
$freqKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore'
$prev = $null
try {
  $prev = (Get-ItemProperty -Path $freqKey -Name SystemRestorePointCreationFrequency -EA SilentlyContinue).SystemRestorePointCreationFrequency
  New-ItemProperty -Path $freqKey -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force -EA Stop | Out-Null
} catch { }

try {
  Checkpoint-Computer -Description '%DESC%' -RestorePointType 'MODIFY_SETTINGS' -EA Stop
  Write-Output 'OK'
} catch {
  Write-Output ('ERR=' + $_.Exception.Message)
} finally {
  try {
    if ($null -ne $prev) {
      Set-ItemProperty -Path $freqKey -Name SystemRestorePointCreationFrequency -Value $prev -EA SilentlyContinue
    } else {
      Remove-ItemProperty -Path $freqKey -Name SystemRestorePointCreationFrequency -EA SilentlyContinue
    }
  } catch { }
}
"""

_PS_STATUS = r"""
$out = @{}
try {
  $drv = Get-WmiObject -Namespace 'root\default' -Class SystemRestoreConfig -EA Stop
  $out.Enabled = $true
} catch {
  # SystemRestoreConfig no existe en todas las ediciones; se deduce por los puntos.
  $out.Enabled = $null
}
try {
  $p = Get-ComputerRestorePoint -EA Stop | Sort-Object CreationTime -Descending | Select-Object -First 1
  if ($p) {
    $out.LastDescription = $p.Description
    $out.LastCreation    = $p.CreationTime
    $out.Enabled         = $true
  } else {
    $out.LastCreation = $null
  }
} catch { $out.LastCreation = $null }
$out | ConvertTo-Json -Compress -Depth 2
"""


def _clean(text: str) -> str:
    """La descripción va dentro de comillas simples de PowerShell."""
    return (text or "Punto de PC Guardian").replace("'", "").replace("\r", " ").replace("\n", " ")[:200]


def create_restore_point(description: str = "PC Guardian - antes de un cambio") -> dict:
    """Crea un punto de restauración. Nunca lanza; informa de por qué no pudo."""
    script = _PS_CREATE.replace("%DESC%", _clean(description))
    # Checkpoint-Computer puede tardar bastante en equipos con disco lento.
    res = run_ps(script, timeout=180)

    if res.timed_out:
        return {"success": False, "message": "La creación del punto de restauración tardó demasiado."}

    salida = res.combined
    if "OK" in res.stdout:
        return {"success": True, "message": "Punto de restauración creado."}

    if "ERR=" in salida:
        detalle = salida.split("ERR=", 1)[1].splitlines()[0].strip()
    else:
        detalle = salida[:200]

    bajo = detalle.lower()
    if res.needs_admin or "denied" in bajo or "denegado" in bajo:
        return {"success": False,
                "message": "Se necesitan permisos de administrador para crear puntos de restauración."}
    if "disabled" in bajo or "deshabilit" in bajo or "shadow" in bajo:
        return {"success": False,
                "message": "La protección del sistema está desactivada en esta unidad. "
                           "Actívala en Propiedades del sistema › Protección del sistema."}
    return {"success": False, "message": detalle or "No se pudo crear el punto de restauración."}


def restore_status() -> dict:
    datos = run_ps_json(_PS_STATUS, timeout=45, default={}) or {}
    if isinstance(datos, list):
        datos = datos[0] if datos else {}
    return {
        "enabled": datos.get("Enabled"),
        "last_creation": datos.get("LastCreation"),
        "last_description": datos.get("LastDescription"),
    }
