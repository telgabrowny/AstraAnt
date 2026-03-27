"""Model builder — compiles OpenSCAD .scad files to visual models for the GUI.

Single source of truth: the same .scad files that define 3D-printable parts
also generate the visual models used in the Ursina simulation.

Pipeline: .scad -> OpenSCAD CLI -> .stl -> trimesh -> .obj -> Ursina

Usage:
    from astraant.model_builder import build_all_models, get_model_path
    build_all_models()  # Compile all .scad to .obj
    path = get_model_path("worker_chassis")  # Get path for Ursina to load
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Any

SCAD_DIR = Path(__file__).parent.parent / "scad"
MODELS_DIR = Path(__file__).parent.parent / "models"  # Output directory for .obj files
OPENSCAD_PATHS = [
    "openscad",                              # In PATH
    "C:/Program Files/OpenSCAD/openscad.com",
    "C:/Program Files/OpenSCAD/openscad.exe",
    "/usr/bin/openscad",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
]


def _find_openscad() -> str | None:
    """Find the OpenSCAD executable."""
    for path in OPENSCAD_PATHS:
        if shutil.which(path):
            return path
        if Path(path).exists():
            return path
    return None


def compile_scad_to_stl(scad_path: Path, stl_path: Path) -> bool:
    """Compile a .scad file to .stl using OpenSCAD CLI."""
    openscad = _find_openscad()
    if openscad is None:
        print("WARNING: OpenSCAD not found. Install from https://openscad.org/")
        return False

    stl_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [openscad, "-o", str(stl_path), str(scad_path)],
            capture_output=True, text=True, timeout=300,  # 5 min for complex models
        )
        if result.returncode != 0:
            print(f"OpenSCAD error for {scad_path.name}: {result.stderr[:200]}")
            return False
        return stl_path.exists() and stl_path.stat().st_size > 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Failed to run OpenSCAD: {e}")
        return False


def convert_stl_to_obj(stl_path: Path, obj_path: Path) -> bool:
    """Convert .stl to .obj using trimesh."""
    try:
        import trimesh
        mesh = trimesh.load(str(stl_path))
        obj_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(obj_path), file_type="obj")
        return obj_path.exists()
    except ImportError:
        print("WARNING: trimesh not installed. Run: pip install trimesh")
        return False
    except Exception as e:
        print(f"Trimesh conversion error: {e}")
        return False


def build_model(scad_name: str) -> Path | None:
    """Build a single model: .scad -> .stl -> .obj

    Args:
        scad_name: Name without extension (e.g., "worker_chassis")

    Returns:
        Path to the .obj file, or None if build failed.
    """
    scad_path = SCAD_DIR / f"{scad_name}.scad"
    if not scad_path.exists():
        # Try generating it first
        from .scad_generator import generate_tool_scad, TOOL_GENERATORS
        if scad_name in TOOL_GENERATORS:
            SCAD_DIR.mkdir(parents=True, exist_ok=True)
            scad_path.write_text(TOOL_GENERATORS[scad_name]())
        else:
            print(f"No .scad file found for: {scad_name}")
            return None

    stl_path = MODELS_DIR / f"{scad_name}.stl"
    obj_path = MODELS_DIR / f"{scad_name}.obj"

    # Check if .obj is newer than .scad (skip rebuild if up-to-date)
    if obj_path.exists() and scad_path.exists():
        if obj_path.stat().st_mtime > scad_path.stat().st_mtime:
            return obj_path  # Already up to date

    print(f"Building {scad_name}: .scad -> .stl -> .obj")

    if not compile_scad_to_stl(scad_path, stl_path):
        return None
    if not convert_stl_to_obj(stl_path, obj_path):
        return None

    print(f"  -> {obj_path}")
    return obj_path


def build_all_models() -> list[Path]:
    """Build all .scad files in the scad directory to .obj models."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    built = []

    if not SCAD_DIR.exists():
        # Generate .scad files first
        from .scad_generator import generate_all_tools
        generate_all_tools()

    for scad_file in sorted(SCAD_DIR.glob("*.scad")):
        name = scad_file.stem
        result = build_model(name)
        if result:
            built.append(result)

    return built


def get_model_path(model_name: str) -> Path | None:
    """Get the path to a compiled .obj model, building if necessary."""
    obj_path = MODELS_DIR / f"{model_name}.obj"
    if obj_path.exists():
        return obj_path
    # Try building it
    return build_model(model_name)


def models_available() -> list[str]:
    """List all available compiled models."""
    if not MODELS_DIR.exists():
        return []
    return [f.stem for f in MODELS_DIR.glob("*.obj")]
