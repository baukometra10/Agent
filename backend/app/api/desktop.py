"""Desktop app download — prefers built installers, else source Electron shell zip."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter(prefix="/system/desktop", tags=["desktop"])

_ROOT = Path(__file__).resolve().parents[3]  # Agent/
_DESKTOP = _ROOT / "desktop"
_DIST = _DESKTOP / "dist"
_PUBLIC = _ROOT / "frontend" / "public" / "downloads"


def _find_built(platform: str) -> Path | None:
    patterns = {
        "windows": ["*win*.zip", "*Windows*.zip", "Spixa*.exe", "*.exe"],
        "macos": ["*mac*.zip", "*darwin*.zip", "*.dmg"],
        "linux": ["*linux*.zip", "*AppImage*", "*.AppImage"],
    }
    for root in (_PUBLIC, _DIST):
        if not root.exists():
            continue
        for pat in patterns.get(platform, []):
            hits = sorted(root.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
            if hits:
                return hits[0]
    return None


@router.get("/releases")
async def desktop_releases():
    platforms = []
    for pid, label in (("windows", "Windows"), ("macos", "macOS"), ("linux", "Linux")):
        built = _find_built(pid)
        platforms.append(
            {
                "id": pid,
                "label": label,
                "arch": "x64",
                "format": built.suffix.lstrip(".") if built else "zip",
                "built": bool(built),
                "artifact": built.name if built else f"spixa-desktop-{pid}.zip",
                "download_path": f"/system/desktop/download/{pid}",
                "notes": (
                    "مثبت جاهز من electron-builder"
                    if built
                    else "حزمة Electron — بعد التنزيل: npm install && npm start أو شغّل scripts/build-desktop.ps1"
                ),
            }
        )
    return {
        "product": "Spixa",
        "company": "Suppix AI",
        "tagline_ar": "نفس مساحة العمل على الويب وسطح المكتب",
        "web_app": "http://localhost:3000/ide",
        "build_script": "scripts/build-desktop.ps1",
        "platforms": platforms,
        "requires": ["Node.js 20+ لبناء الحزم", "Spixa API + UI"],
    }


def _zip_desktop(platform: str) -> bytes:
    if not _DESKTOP.exists():
        raise FileNotFoundError("desktop shell missing")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in _DESKTOP.rglob("*"):
            if path.is_dir():
                continue
            if "node_modules" in path.parts or "dist" in path.parts or path.suffix == ".zip":
                continue
            arc = Path("spixa-desktop") / path.relative_to(_DESKTOP)
            zf.write(path, arcname=str(arc).replace("\\", "/"))
        zf.writestr(
            "spixa-desktop/PLATFORM.txt",
            f"Spixa Desktop · {platform}\nSuppix AI\nnpm install && npm start\nnpm run dist  # NSIS/DMG/AppImage\n",
        )
        zf.writestr(
            "spixa-desktop/INSTALL.txt",
            "Windows: npm run dist  -> dist/*.exe (NSIS)\nmacOS: npm run dist -> dist/*.dmg\nLinux: npm run dist -> dist/*.AppImage\n",
        )
    return buf.getvalue()


@router.get("/download/{platform}")
async def download_desktop(platform: str):
    plat = platform.lower().strip()
    if plat in {"win"}:
        plat = "windows"
    if plat in {"mac"}:
        plat = "macos"
    if plat not in {"windows", "macos", "linux"}:
        plat = "windows"

    built = _find_built(plat)
    if built and built.exists():
        media = "application/octet-stream"
        if built.suffix == ".zip":
            media = "application/zip"
        elif built.suffix == ".dmg":
            media = "application/x-apple-diskimage"
        return FileResponse(built, media_type=media, filename=built.name)

    try:
        data = _zip_desktop(plat)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="desktop_not_ready") from exc
    filename = f"spixa-desktop-{plat}.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
