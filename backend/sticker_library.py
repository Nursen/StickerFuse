"""Persistent sticker library: folders and copied PNGs independent of Studio /outputs/stickers."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_VERSION = 1
SAFE_FOLDER_NAME = re.compile(r"^[\w\s\-'.&,]{1,80}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StickerLibrary:
    def __init__(self, project_root: Path) -> None:
        self.root = project_root / "outputs" / "sticker_library"
        self.data_dir = self.root / "data"
        self.manifest_path = self.root / "manifest.json"
        self.stickers_source = project_root / "outputs" / "stickers"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_manifest(self) -> dict:
        self.ensure_dirs()
        if not self.manifest_path.is_file():
            default = {"version": MANIFEST_VERSION, "folders": [], "items": []}
            self.save_manifest(default)
            return default
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"version": MANIFEST_VERSION, "folders": [], "items": []}
        data.setdefault("version", MANIFEST_VERSION)
        data.setdefault("folders", [])
        data.setdefault("items", [])
        return data

    def save_manifest(self, data: dict) -> None:
        self.ensure_dirs()
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)

    def _folder_path(self, folder_id: str) -> Path:
        return (self.data_dir / folder_id).resolve()

    def _validate_folder_id(self, folder_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{12}", folder_id):
            raise ValueError("Invalid folder id")
        p = self._folder_path(folder_id)
        try:
            p.relative_to(self.data_dir.resolve())
        except ValueError as exc:
            raise ValueError("Invalid folder path") from exc
        return p

    def list_all(self) -> dict:
        return self.load_manifest()

    def create_folder(self, name: str) -> dict:
        n = (name or "").strip()
        if not n or not SAFE_FOLDER_NAME.match(n):
            raise ValueError(
                "Folder name must be 1–80 characters and may include letters, numbers, spaces, "
                "and - ' . & ,"
            )
        m = self.load_manifest()
        folder_id = uuid.uuid4().hex[:12]
        folder = {"id": folder_id, "name": n, "created_at": _utc_now()}
        m["folders"].append(folder)
        self._folder_path(folder_id).mkdir(parents=True, exist_ok=True)
        self.save_manifest(m)
        return folder

    def delete_folder(self, folder_id: str) -> None:
        p = self._validate_folder_id(folder_id)
        m = self.load_manifest()
        m["folders"] = [f for f in m["folders"] if f["id"] != folder_id]
        m["items"] = [it for it in m["items"] if it["folder_id"] != folder_id]
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        self.save_manifest(m)

    def _validate_source_sticker(self, filename: str) -> Path:
        safe = Path(filename).name
        if safe != filename or ".." in filename:
            raise ValueError("Invalid filename")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", safe):
            raise ValueError("Invalid filename")
        base = self.stickers_source.resolve()
        path = (base / safe).resolve()
        try:
            path.relative_to(base)
        except ValueError as exc:
            raise ValueError("Invalid path") from exc
        if not path.is_file():
            raise ValueError("Source sticker not found (generate or download it first)")
        return path

    def add_item_from_stickers_folder(self, folder_id: str, source_filename: str) -> dict:
        self._validate_folder_id(folder_id)
        if not self._folder_path(folder_id).is_dir():
            raise ValueError("Folder not found")

        src = self._validate_source_sticker(source_filename)
        item_id = uuid.uuid4().hex[:12]
        dest_name = f"{item_id}.png"
        dest_dir = self._folder_path(folder_id)
        dest = dest_dir / dest_name
        shutil.copy2(src, dest)

        m = self.load_manifest()
        if not any(f["id"] == folder_id for f in m["folders"]):
            if dest.is_file():
                dest.unlink()
            raise ValueError("Folder not found in manifest")

        item = {
            "id": item_id,
            "folder_id": folder_id,
            "filename": dest_name,
            "source_label": source_filename,
            "created_at": _utc_now(),
        }
        m["items"].append(item)
        self.save_manifest(m)
        return item

    def _validate_item_id(self, item_id: str) -> None:
        if not re.fullmatch(r"[a-f0-9]{12}", item_id):
            raise ValueError("Invalid item id")

    def move_item(self, item_id: str, new_folder_id: str) -> dict:
        self._validate_item_id(item_id)
        self._validate_folder_id(new_folder_id)
        new_dir = self._folder_path(new_folder_id)
        if not new_dir.is_dir():
            raise ValueError("Destination folder not found")

        m = self.load_manifest()
        item = next((it for it in m["items"] if it["id"] == item_id), None)
        if not item:
            raise ValueError("Item not found")
        if item["folder_id"] == new_folder_id:
            return item

        old_dir = self._folder_path(item["folder_id"])
        fname = item["filename"]
        old_path = old_dir / fname
        new_path = new_dir / fname
        if not old_path.is_file():
            raise ValueError("Sticker file missing on disk")

        shutil.move(str(old_path), str(new_path))
        item["folder_id"] = new_folder_id
        self.save_manifest(m)
        return item

    def delete_item(self, item_id: str) -> None:
        self._validate_item_id(item_id)
        m = self.load_manifest()
        item = next((it for it in m["items"] if it["id"] == item_id), None)
        if not item:
            raise ValueError("Item not found")

        p = self._folder_path(item["folder_id"]) / item["filename"]
        if p.is_file():
            p.unlink()
        m["items"] = [it for it in m["items"] if it["id"] != item_id]
        self.save_manifest(m)


def get_library(project_root: Path) -> StickerLibrary:
    return StickerLibrary(project_root)
