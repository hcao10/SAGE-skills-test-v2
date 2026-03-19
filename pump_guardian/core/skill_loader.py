from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Dict, List


def discover_skills(skills_root: Path) -> List[Dict[str, str]]:
    """Discover skills from folder names only (metadata-level discovery)."""
    skills: List[Dict[str, str]] = []
    if not skills_root.exists():
        return skills

    for child in skills_root.iterdir():
        if child.is_dir():
            skills.append(
                {
                    "skill_id": child.name,
                    "name": child.name.replace("_", " ").title(),
                    "path": str(child),
                }
            )
    return skills


def load_skill_markdown(skill_dir: Path) -> str:
    skill_md_path = skill_dir / "SKILL.md"
    return skill_md_path.read_text(encoding="utf-8")


def load_reference_json(skill_dir: Path, filename: str) -> dict:
    ref_path = skill_dir / "references" / filename
    with ref_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_asset_template(skill_dir: Path, filename: str) -> str:
    template_path = skill_dir / "assets" / filename
    return template_path.read_text(encoding="utf-8")


def load_diag_tool(skill_dir: Path, script_name: str = "diag_tool.py") -> ModuleType:
    script_path = skill_dir / "scripts" / script_name
    spec = importlib.util.spec_from_file_location("diag_tool", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load diagnostic tool from {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
