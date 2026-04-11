import subprocess
import json
import re


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
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=90
        )
        raw = result.stdout.strip()
        if not raw:
            raw = "[]"

        try:
            updates_raw = json.loads(raw)
        except json.JSONDecodeError:
            updates_raw = []

        if isinstance(updates_raw, dict):
            updates_raw = [updates_raw]

    except subprocess.TimeoutExpired:
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

    cmd = (
        r"$s = New-Object -ComObject Microsoft.Update.Session;"
        r"$sr = $s.CreateUpdateSearcher();"
        r"try {"
        r"  $r = $sr.Search(\"UpdateID='" + update_id + r"' and IsInstalled=0\");"
        r"  if ($r.Updates.Count -eq 0) { Write-Output 'NOT_FOUND'; exit };"
        r"  $dl = $s.CreateUpdateDownloader();"
        r"  $dl.Updates = $r.Updates;"
        r"  $dl.Download() | Out-Null;"
        r"  $inst = $s.CreateUpdateInstaller();"
        r"  $inst.Updates = $r.Updates;"
        r"  $res = $inst.Install();"
        r"  Write-Output ('RC=' + $res.ResultCode);"
        r"  Write-Output ('REBOOT=' + $res.RebootRequired);"
        r"} catch { Write-Output ('ERR=' + $_.Exception.Message) }"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=600,
        )
        output = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        full_output = (output + "\n" + stderr).strip()

        if "NOT_FOUND" in output:
            return {"success": False, "message": "La actualización ya no figura como pendiente.", "output": full_output}
        if "ERR=" in output:
            err_msg = output.split("ERR=", 1)[1].splitlines()[0].strip()
            if "0x80070005" in err_msg or "acceso" in err_msg.lower() or "access" in err_msg.lower():
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

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "La instalación tardó demasiado y fue cancelada.", "output": ""}
    except Exception as exc:
        return {"success": False, "message": str(exc), "output": ""}
