"""Pack manager — persistent storage for sticker packs.

A Pack contains:
- name: user-chosen name ("Bridgerton Vibes")
- ideas: list of sticker ideas (from AI brainstorm + manual entry)
- stickers: list of generated sticker filenames
- created_at, updated_at timestamps
- topic: optional source topic

Stored as JSON files in outputs/packs/
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class PackManager:
    def __init__(self, root: Path):
        self._dir = root / "outputs" / "packs"
        self._dir.mkdir(parents=True, exist_ok=True)

    def create_pack(self, name: str, topic: str = "") -> dict:
        """Create a new empty pack."""
        pack_id = uuid.uuid4().hex[:12]
        pack = {
            "id": pack_id,
            "name": name,
            "topic": topic,
            "ideas": [],  # list of idea dicts
            "stickers": [],  # list of {filename, idea_ref, created_at}
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._save(pack)
        return pack

    def list_packs(self) -> list[dict]:
        """List all packs (summary: id, name, topic, idea count, sticker count, dates)."""
        packs = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                packs.append({
                    "id": data["id"],
                    "name": data["name"],
                    "topic": data.get("topic", ""),
                    "idea_count": len(data.get("ideas", [])),
                    "sticker_count": len(data.get("stickers", [])),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })
            except Exception:
                continue
        return packs

    def get_pack(self, pack_id: str) -> dict:
        """Get full pack data."""
        path = self._dir / f"{pack_id}.json"
        if not path.is_file():
            raise ValueError(f"Pack not found: {pack_id}")
        return json.loads(path.read_text())

    def add_idea(self, pack_id: str, idea: dict) -> dict:
        """Add an idea to a pack. Returns the updated pack."""
        pack = self.get_pack(pack_id)
        # Give each idea a unique id
        idea["id"] = idea.get("id") or uuid.uuid4().hex[:8]
        idea["added_at"] = datetime.now(tz=timezone.utc).isoformat()
        pack["ideas"].append(idea)
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def add_ideas_batch(self, pack_id: str, ideas: list[dict]) -> dict:
        """Add multiple ideas to a pack."""
        pack = self.get_pack(pack_id)
        for idea in ideas:
            idea["id"] = idea.get("id") or uuid.uuid4().hex[:8]
            idea["added_at"] = datetime.now(tz=timezone.utc).isoformat()
            pack["ideas"].append(idea)
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def remove_idea(self, pack_id: str, idea_id: str) -> dict:
        """Remove an idea from a pack."""
        pack = self.get_pack(pack_id)
        pack["ideas"] = [i for i in pack["ideas"] if i.get("id") != idea_id]
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def add_sticker(self, pack_id: str, filename: str, idea_ref: str = "") -> dict:
        """Record a generated sticker in the pack."""
        pack = self.get_pack(pack_id)
        pack["stickers"].append({
            "filename": filename,
            "idea_ref": idea_ref,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def remove_sticker(self, pack_id: str, filename: str) -> dict:
        """Remove a sticker from the pack."""
        pack = self.get_pack(pack_id)
        pack["stickers"] = [s for s in pack["stickers"] if s["filename"] != filename]
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def update_pack(self, pack_id: str, name: str = None, topic: str = None) -> dict:
        """Update pack metadata."""
        pack = self.get_pack(pack_id)
        if name is not None:
            pack["name"] = name
        if topic is not None:
            pack["topic"] = topic
        pack["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save(pack)
        return pack

    def delete_pack(self, pack_id: str):
        """Delete a pack."""
        path = self._dir / f"{pack_id}.json"
        if path.is_file():
            path.unlink()

    def export_zip(self, pack_id: str, stickers_dir: Path) -> Path:
        """Create a zip of all stickers in the pack. Returns path to zip file."""
        import zipfile
        pack = self.get_pack(pack_id)
        zip_path = self._dir / f"{pack_id}_export.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for sticker in pack.get("stickers", []):
                src = stickers_dir / sticker["filename"]
                if src.is_file():
                    zf.write(src, sticker["filename"])

        return zip_path

    def _save(self, pack: dict):
        path = self._dir / f"{pack['id']}.json"
        path.write_text(json.dumps(pack, indent=2, ensure_ascii=False))
