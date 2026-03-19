from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Any, List, Mapping, Optional


def _merge_minimax_from_flat_mapping(data: Mapping[str, Any]) -> None:
    keys = ("MINIMAX_API_KEY", "MINIMAX_API_BASE", "MINIMAX_MODEL")
    for k in keys:
        if os.environ.get(k):
            continue
        if k not in data:
            continue
        val = data[k]
        if val is None:
            continue
        s = str(val).strip().strip('"').strip("'")
        if s:
            os.environ[k] = s

    mini = data.get("minimax") if hasattr(data, "get") else None
    if isinstance(mini, Mapping):
        alias = {
            "MINIMAX_API_KEY": mini.get("api_key") or mini.get("API_KEY"),
            "MINIMAX_API_BASE": mini.get("api_base") or mini.get("API_BASE"),
            "MINIMAX_MODEL": mini.get("model") or mini.get("MODEL"),
        }
        for k, v in alias.items():
            if v is None:
                continue
            s = str(v).strip().strip('"').strip("'")
            if s and not os.environ.get(k):
                os.environ[k] = s


def _read_text_flexible(path: Path) -> Optional[str]:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return None


def merge_env_file_into_environ(path: Path) -> None:
    """
    Parse `.env` without requiring `python-dotenv` (Streamlit demos often miss that dep).
    Only sets variables that are not already present in os.environ (same as load_dotenv override=False).
    """
    if not path.is_file():
        return
    text = _read_text_flexible(path)
    if text is None:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        if os.environ.get(key):
            continue
        if value != "":
            os.environ[key] = value


def env_file_candidates(app_dir: Path) -> List[Path]:
    return [
        app_dir / ".env",
        Path.cwd() / ".env",
        app_dir.parent / ".env",
        app_dir / ".env.txt",
        Path.cwd() / ".env.txt",
    ]


def load_dotenv_candidates(app_dir: Path) -> None:
    """
    Load `.env` from several likely locations (first wins per variable; dotenv default override=False).
    Fixes: running Streamlit from a parent folder so cwd != app_dir, or `.env` placed one level up.
    Always runs a built-in parser; uses `python-dotenv` first when installed.
    """
    seen: set[Path] = set()
    for path in env_file_candidates(app_dir):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.is_file():
            continue
        try:
            from dotenv import load_dotenv

            load_dotenv(path, override=False)
        except ImportError:
            pass
        merge_env_file_into_environ(path)


def merge_streamlit_secrets_toml_file(path: Path) -> None:
    """
    Read `.streamlit/secrets.toml` next to the app project and merge into os.environ.
    Use this so config works even when `streamlit run` is started from a parent directory
    (Streamlit only auto-loads secrets from the *current working directory*).
    """
    if not path.is_file():
        return
    try:
        import tomllib
    except ImportError:
        return
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except OSError:
        return
    if isinstance(data, dict):
        _merge_minimax_from_flat_mapping(data)


def load_minimax_config_files(app_dir: Path) -> None:
    """Load `.env` candidates + `app_dir/.streamlit/secrets.toml` into environment."""
    load_dotenv_candidates(app_dir)
    merge_streamlit_secrets_toml_file(app_dir / ".streamlit" / "secrets.toml")


def merge_streamlit_secrets_into_environ(secrets: Any) -> None:
    """
    Copy Streamlit `st.secrets` into os.environ when the env var is not already set.
    Supports flat keys: MINIMAX_API_KEY, MINIMAX_API_BASE, MINIMAX_MODEL.
    Also supports nested [minimax] table in secrets.toml.
    """
    keys = ("MINIMAX_API_KEY", "MINIMAX_API_BASE", "MINIMAX_MODEL")

    for k in keys:
        if os.environ.get(k):
            continue
        try:
            val = secrets[k]
        except (KeyError, TypeError):
            continue
        if val is not None and str(val).strip():
            os.environ[k] = str(val).strip().strip('"').strip("'")

    try:
        mini = secrets["minimax"]
    except (KeyError, TypeError):
        mini = None

    if isinstance(mini, Mapping):
        alias = {
            "MINIMAX_API_KEY": mini.get("api_key") or mini.get("API_KEY"),
            "MINIMAX_API_BASE": mini.get("api_base") or mini.get("API_BASE"),
            "MINIMAX_MODEL": mini.get("model") or mini.get("MODEL"),
        }
        for k, v in alias.items():
            if v is not None and str(v).strip() and not os.environ.get(k):
                os.environ[k] = str(v).strip().strip('"').strip("'")


def minimax_api_key() -> Optional[str]:
    v = os.environ.get("MINIMAX_API_KEY")
    if v is None:
        return None
    s = str(v).strip().strip('"').strip("'")
    return s or None


def config_diagnostics(app_dir: Path) -> List[str]:
    """Human-readable lines for sidebar troubleshooting."""
    lines: List[str] = []
    lines.append(f"app_dir: {app_dir}")
    lines.append(f"cwd: {Path.cwd()}")
    for label, p in [
        (".env (app)", app_dir / ".env"),
        (".env (cwd)", Path.cwd() / ".env"),
        (".env (parent)", app_dir.parent / ".env"),
        (".env.txt (app)", app_dir / ".env.txt"),
        ("secrets.toml", app_dir / ".streamlit" / "secrets.toml"),
    ]:
        try:
            ok = p.resolve().is_file()
        except OSError:
            ok = False
        lines.append(f"[{'OK' if ok else '--'}] {label}: {p}")
    k = minimax_api_key()
    if k:
        tail = k[-4:] if len(k) >= 4 else k
        lines.append(f"API key (env): loaded (len={len(k)}, suffix …{tail})")
    else:
        lines.append("API key (env): not loaded")
    lines.append(
        "python-dotenv: installed"
        if importlib.util.find_spec("dotenv") is not None
        else "python-dotenv: not installed (using built-in .env parser)"
    )
    return lines
