import json
import re

from ._shell import run_ps, run_ps_json


def check_windows_updates() -> dict:
    cmd = r"""
$s = New-Object -ComObject Microsoft.Update.Session
$sr = $s.CreateUpdateSearcher()
try {
    $r = $sr.Search("IsInstalled=0 and Type='Software'")
    $r.Updates | Select-Object Title,
        @{n='Severity';e={if($_.MsrcSeverity){$_.MsrcSeverity}else{'Low'}}},
        @{n='SizeMB';e={[math]::Round($_.MaxDownloadSize/1MB,1)}},
        @{n='UpdateID';e={$_.Identity.UpdateID}},
        @{n='KBArticleIDs';e={($_.KBArticleIDs | ForEach-Object {$_}) -join ','}},
        @{n='Description';e={if($_.Description){$_.Description.Substring(0,[math]::Min(400,$_.Description.Length))}else{''}}},
        IsDownloaded | ConvertTo-Json -Compress -Depth 2
} catch { '[]' }
"""
    try:
        updates_raw = run_ps_json(cmd, timeout=90, default=[]) or []
    except TimeoutError:
        return {
            "status": "warning",
            "title": "Actualizaciones Windows",
            "summary": "La consulta a Windows Update superó el tiempo límite.",
            "issue_count": 0,
            "items": [],
        }
    except Exception as exc:
        return {
            "status": "warning",
            "title": "Actualizaciones Windows",
            "summary": f"No se pudo consultar Windows Update: {exc}",
            "issue_count": 0,
            "items": [],
        }

    items = []
    danger_count = 0
    warning_count = 0

    for u in updates_raw:
        title = u.get("Title", "Actualización desconocida")
        severity = (u.get("Severity") or "Low").strip()
        size_mb = u.get("SizeMB", 0) or 0
        update_id = u.get("UpdateID", "")
        description = u.get("Description", "") or ""

        # Extraer números KB del campo KBArticleIDs y como fallback del título
        kb_raw = u.get("KBArticleIDs", "") or ""
        kb_numbers = [kb.strip() for kb in kb_raw.split(",") if kb.strip()]
        if not kb_numbers:
            kb_numbers = re.findall(r'KB(\d+)', title)

        # URL canónica de soporte Microsoft
        kb_url = f"https://support.microsoft.com/kb/{kb_numbers[0]}" if kb_numbers else ""

        if severity in ("Critical", "Important"):
            status = "danger"
            danger_count += 1
        elif severity == "Moderate":
            status = "warning"
            warning_count += 1
        else:
            status = "ok"

        size_str = f"{size_mb} MB" if size_mb else "—"
        items.append({
            "name": title,
            "status": status,
            "value": size_str,
            "message": f"Gravedad: {severity}",
            "detail": description,
            "update_id": update_id,
            "kb_numbers": kb_numbers,
            "kb_url": kb_url,
        })

    total = len(items)
    if total == 0:
        overall_status = "ok"
        summary = "El sistema está completamente actualizado."
        issue_count = 0
    elif danger_count > 0:
        overall_status = "danger"
        summary = f"{danger_count} actualización(es) crítica(s) pendiente(s) de {total} en total."
        issue_count = danger_count
    else:
        overall_status = "warning"
        summary = f"{total} actualización(es) pendiente(s) (sin críticas)."
        issue_count = warning_count

    return {
        "status": overall_status,
        "title": "Actualizaciones Windows",
        "summary": summary,
        "issue_count": issue_count,
        "items": items,
    }


def apply_windows_update(update_id: str) -> dict:
    """Descarga e instala una actualización concreta de Windows por su GUID.
    Requiere que la aplicación se ejecute con privilegios de administrador.
    """
    if not re.match(r'^[0-9a-fA-F\-]{36}$', update_id):
        return {"success": False, "message": "ID de actualización no válido.", "output": ""}

    # El GUID ya está validado arriba; -EncodedCommand elimina además cualquier
    # problema de comillas o escapado al pasar el script al shell.
    cmd = (
        "$s = New-Object -ComObject Microsoft.Update.Session;"
        "$sr = $s.CreateUpdateSearcher();"
        "try {"
        "  $r = $sr.Search(\"UpdateID='" + update_id + "' and IsInstalled=0\");"
        "  if ($r.Updates.Count -eq 0) { Write-Output 'NOT_FOUND'; exit };"
        "  $dl = $s.CreateUpdateDownloader();"
        "  $dl.Updates = $r.Updates;"
        "  $dl.Download() | Out-Null;"
        "  $inst = $s.CreateUpdateInstaller();"
        "  $inst.Updates = $r.Updates;"
        "  $res = $inst.Install();"
        "  Write-Output ('RC=' + $res.ResultCode);"
        "  Write-Output ('REBOOT=' + $res.RebootRequired);"
        "} catch { Write-Output ('ERR=' + $_.Exception.Message) }"
    )

    res = run_ps(cmd, timeout=600)
    if res.timed_out:
        return {"success": False, "message": "La instalación tardó demasiado y fue cancelada.", "output": ""}
    if res.error:
        return {"success": False, "message": res.error, "output": ""}

    output = res.stdout.strip()
    full_output = res.combined

    if "NOT_FOUND" in output:
        return {"success": False, "message": "La actualización ya no figura como pendiente.", "output": full_output}
    if "ERR=" in output:
        err_msg = output.split("ERR=", 1)[1].splitlines()[0].strip()
        if res.needs_admin or "0x80070005" in err_msg:
            return {"success": False, "message": "Se necesitan permisos de administrador para instalar actualizaciones. Reinicia PC Guardian como administrador.", "output": full_output}
        return {"success": False, "message": err_msg, "output": full_output}

    # ResultCode 2 = Succeeded, 3 = Succeeded with errors
    if "RC=2" in output or "RC=3" in output:
        reboot = "REBOOT=True" in output
        msg = "Actualización instalada correctamente."
        if reboot:
            msg += " Es necesario reiniciar el equipo para completar la instalación."
        return {"success": True, "message": msg, "reboot_required": reboot, "output": full_output}

    return {"success": False, "message": "La actualización no pudo completarse (RC inesperado).", "output": full_output}
