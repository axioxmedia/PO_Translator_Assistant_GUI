"""Kepler 186F PO Translator Desk — extract untranslated .po entries and apply by msgid."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from axioxmedia import AIO_BRAND, aio_logo_png, aio_watermark, apply_hwnd_icon, axiox_window_title

APP_VERSION = "1.3.0"
PO_BLOCK = re.compile(
    r'msgid "(?P<msgid>(?:\\.|[^"])*)"\nmsgstr "(?P<msgstr>(?:\\.|[^"])*)"',
    re.MULTILINE,
)


def app_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


ROOT = app_root()
STATIC = ROOT / "static"

app = FastAPI(title="Kepler 186F PO Translator Desk", version=APP_VERSION)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


class PathBody(BaseModel):
    po_path: str = ""
    json_path: str = ""
    output_path: str = ""


class PickBody(BaseModel):
    mode: str = Field(pattern="^(open-po|open-json|save-json|save-po)$")
    suggest: str = ""


def default_root() -> str:
    if os.name == "nt":
        d = Path("D:/")
        if d.exists():
            return str(Path("D:/Projects"))
        return str(Path.home() / "Projects")
    for candidate in ("/mnt/d/Projects", "/media/d/Projects"):
        if Path(candidate).parent.exists():
            return candidate
    return str(Path.home() / "Projects")


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


LOG_FILE = runtime_dir() / "po_translator_desk.log"


def write_log(message: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except OSError:
        pass


def show_error(message: str) -> None:
    write_log(message)
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "PO Translator Desk", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def resolve_existing(path: str, label: str) -> Path:
    text = (path or "").strip()
    if not text:
        raise HTTPException(400, f"请先选择{label}")
    target = Path(text).expanduser()
    if not target.is_file():
        raise HTTPException(400, f"{label}不存在：{target}")
    return target


def resolve_output(path: str, label: str) -> Path:
    text = (path or "").strip()
    if not text:
        raise HTTPException(400, f"请先选择{label}")
    target = Path(text).expanduser()
    if not target.parent.exists():
        raise HTTPException(400, f"{label}所在目录不存在：{target.parent}")
    return target


def parse_po_file(filepath: Path) -> tuple[list[dict[str, Any]], str]:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    entries: list[dict[str, Any]] = []
    for match in PO_BLOCK.finditer(content):
        msgid = match.group("msgid").replace('\\"', '"')
        msgstr = match.group("msgstr").replace('\\"', '"')
        entries.append(
            {
                "msgid": msgid,
                "msgstr": msgstr,
                "needs_translation": (not msgstr or msgstr == msgid),
            }
        )
    return entries, content


def stats_of(entries: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(entries)
    translated = sum(1 for item in entries if item["msgstr"] and item["msgstr"] != item["msgid"])
    pending = total - translated
    percent = (translated / total * 100) if total else 0.0
    return {
        "total": total,
        "translated": translated,
        "pending": pending,
        "percent": round(percent, 1),
    }


def suggested_output(po_path: Path) -> str:
    return str(po_path.parent / f"{po_path.stem}.zh_CN.po")


def suggested_json(po_path: Path) -> str:
    return str(po_path.parent / "untranslated.json")


def update_po_header(content: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M%z")
    content = re.sub(r"^Language: .*", "Language: zh_CN", content, flags=re.MULTILINE)
    content = re.sub(r"^PO-Revision-Date: .*", f"PO-Revision-Date: {now}", content, flags=re.MULTILINE)
    return content


def pick_with_tk(mode: str, suggest: str) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    initial = Path(suggest).expanduser() if suggest else Path(default_root())
    initialdir = str(initial.parent if initial.suffix else initial)
    initialfile = initial.name if initial.suffix else ""
    path = ""
    if mode == "open-po":
        path = filedialog.askopenfilename(
            title="选择原始 PO 文件",
            initialdir=initialdir,
            filetypes=[("PO files", "*.po"), ("All files", "*.*")],
        )
    elif mode == "open-json":
        path = filedialog.askopenfilename(
            title="选择翻译 JSON",
            initialdir=initialdir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
    elif mode == "save-json":
        path = filedialog.asksaveasfilename(
            title="保存未翻译内容 JSON",
            defaultextension=".json",
            initialdir=initialdir,
            initialfile=initialfile or "untranslated.json",
            filetypes=[("JSON files", "*.json")],
        )
    elif mode == "save-po":
        path = filedialog.asksaveasfilename(
            title="保存最终 PO",
            defaultextension=".po",
            initialdir=initialdir,
            initialfile=initialfile or "Game.zh_CN.po",
            filetypes=[("PO files", "*.po")],
        )
    root.destroy()
    return path or ""


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/brand/logo.png")
def brand_logo() -> Response:
    return Response(content=aio_logo_png(), media_type="image/png")


@app.get("/favicon.ico")
def brand_favicon() -> Response:
    return Response(content=aio_logo_png(), media_type="image/png")


@app.get("/api/defaults")
def api_defaults() -> dict[str, Any]:
    root = default_root()
    return {
        "dest_root": root,
        "prefer_d": os.name == "nt" and Path("D:/").exists(),
        "platform": sys.platform,
        "is_windows": os.name == "nt",
        "aio_brand": AIO_BRAND,
        "axiox_title": axiox_window_title(),
        "axioxmedia": aio_watermark(),
        "version": APP_VERSION,
    }


@app.post("/api/pick")
def api_pick(req: PickBody) -> dict[str, str]:
    try:
        path = pick_with_tk(req.mode, req.suggest)
    except Exception as exc:
        raise HTTPException(500, f"无法打开系统文件对话框：{exc}") from exc
    payload: dict[str, str] = {"path": path, "mode": req.mode}
    if path and req.mode == "open-po":
        po = Path(path)
        payload["output_path"] = suggested_output(po)
        payload["json_path"] = suggested_json(po)
    return payload


@app.post("/api/inspect")
def api_inspect(req: PathBody) -> dict[str, Any]:
    po = resolve_existing(req.po_path, "原始 PO 文件")
    entries, _ = parse_po_file(po)
    info = stats_of(entries)
    return {
        "po_path": str(po),
        "output_path": suggested_output(po),
        "json_path": suggested_json(po),
        **info,
    }


@app.post("/api/extract")
def api_extract(req: PathBody) -> dict[str, Any]:
    po = resolve_existing(req.po_path, "原始 PO 文件")
    dest = resolve_output(req.json_path, "未翻译 JSON")
    entries, _ = parse_po_file(po)
    untranslated: list[dict[str, Any]] = []
    for idx, entry in enumerate(entries, 1):
        if entry.get("needs_translation") and entry.get("msgid", "").strip():
            untranslated.append({"id": idx, "msgid": entry["msgid"], "msgstr": ""})
    dest.write_text(json.dumps(untranslated, ensure_ascii=False, indent=2), encoding="utf-8")
    write_log(f"extract {len(untranslated)} -> {dest}")
    return {
        "ok": True,
        "count": len(untranslated),
        "json_path": str(dest),
        **stats_of(entries),
    }


@app.post("/api/apply")
def api_apply(req: PathBody) -> dict[str, Any]:
    po = resolve_existing(req.po_path, "原始 PO 文件")
    trans = resolve_existing(req.json_path, "翻译 JSON")
    output = resolve_output(req.output_path, "输出 PO 文件")
    if output.resolve() == po.resolve():
        raise HTTPException(400, "输出路径不能覆盖原始 PO 文件，请另存为新文件")
    entries, content = parse_po_file(po)
    try:
        translations = json.loads(trans.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"JSON 无法解析：{exc}") from exc
    trans_dict: dict[str, str] = {}
    if isinstance(translations, list):
        for item in translations:
            if isinstance(item, dict) and item.get("msgstr") and item.get("msgid"):
                trans_dict[str(item["msgid"])] = str(item["msgstr"])
    elif isinstance(translations, dict):
        for key, value in translations.items():
            if value:
                trans_dict[str(key)] = str(value)
    else:
        raise HTTPException(400, "翻译 JSON 必须是数组，或 msgid→msgstr 对象")

    new_content = content
    translated_count = 0
    for entry in entries:
        if not entry.get("needs_translation"):
            continue
        msgid = entry["msgid"]
        if msgid not in trans_dict:
            continue
        new_msgstr = trans_dict[msgid]
        old_block = f'msgid "{msgid}"\nmsgstr "{entry["msgstr"]}"'
        new_block = f'msgid "{msgid}"\nmsgstr "{new_msgstr}"'
        if old_block in new_content:
            new_content = new_content.replace(old_block, new_block, 1)
            translated_count += 1

    new_content = update_po_header(new_content)
    output.write_text(new_content, encoding="utf-8")
    after, _ = parse_po_file(output)
    write_log(f"apply {translated_count} -> {output}")
    return {
        "ok": True,
        "applied": translated_count,
        "output_path": str(output),
        **stats_of(after),
    }


def _free_port(preferred: int = 8787) -> int:
    import socket

    for port in (preferred, 8788, 8789, 8790, 0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            chosen = int(sock.getsockname()[1])
        except OSError:
            chosen = -1
        finally:
            sock.close()
        if chosen > 0:
            return chosen
    raise RuntimeError("没有可用的本地端口")


def ensure_stdio() -> None:
    """Windowed PyInstaller sets stdout/stderr to None; uvicorn logging needs them."""
    if sys.stdout is None:
        sys.stdout = LOG_FILE.open("a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = LOG_FILE.open("a", encoding="utf-8")


def run_server(host: str, port: int, reload: bool = False) -> None:
    import uvicorn

    ensure_stdio()
    if reload:
        uvicorn.run(app, host=host, port=port, reload=True, log_level="warning", log_config=None)
        return

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        log_config=None,
        lifespan="on",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    server.run()


def wait_ready(url: str, server_error: list[str], timeout: float = 30.0) -> None:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_error:
            raise RuntimeError(server_error[0])
        try:
            with httpx.Client(timeout=0.8, trust_env=False) as http:
                if http.get(url).status_code < 500:
                    return
        except httpx.HTTPError:
            time.sleep(0.2)
    extra = f"\n服务线程错误：{server_error[0]}" if server_error else ""
    raise RuntimeError(f"本地服务启动超时：{url}{extra}\n日志：{LOG_FILE}")


def run_desktop() -> None:
    import traceback
    import webbrowser

    write_log(f"start frozen={getattr(sys, 'frozen', False)} meipass={getattr(sys, '_MEIPASS', '')}")
    write_log(f"static={STATIC} exists={STATIC.exists()}")

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    write_log(f"bind {url}")
    server_error: list[str] = []

    def _serve() -> None:
        try:
            run_server("127.0.0.1", port, reload=False)
        except Exception:
            server_error.append(traceback.format_exc())
            write_log(server_error[-1])

    thread = threading.Thread(target=_serve, name="uvicorn", daemon=True)
    thread.start()
    wait_ready(f"{url}/api/defaults", server_error)

    try:
        import webview

        window = webview.create_window(
            title=axiox_window_title(),
            url=url,
            width=1280,
            height=820,
            min_size=(960, 680),
            background_color="#0b0d12",
        )

        def paint_chrome(_=None) -> None:
            if os.name != "nt":
                return
            try:
                import ctypes

                hwnd = int(window.native.Handle.ToInt32())
                apply_hwnd_icon(hwnd)
                value = ctypes.c_int(1)
                for attr in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                    )
            except Exception as exc:
                write_log(f"dark titlebar skipped: {exc}")

        try:
            window.events.shown += paint_chrome
        except Exception:
            pass
        webview.start()
        return
    except Exception:
        write_log(traceback.format_exc())
        webbrowser.open(url)
        while thread.is_alive():
            thread.join(timeout=0.5)


if __name__ == "__main__":
    import multiprocessing
    import traceback

    multiprocessing.freeze_support()
    ensure_stdio()
    try:
        desktop = "--web" not in sys.argv and os.environ.get("PO_TRANSLATOR_WEB") != "1"
        if desktop:
            run_desktop()
        else:
            run_server("127.0.0.1", _free_port(8787), reload=not getattr(sys, "frozen", False))
    except Exception:
        show_error("启动失败：\n\n" + traceback.format_exc() + f"\n\n日志文件：{LOG_FILE}")
        raise
