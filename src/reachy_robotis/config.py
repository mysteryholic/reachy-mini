import os
import sys
import logging
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlunsplit
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


LOCKED_PROFILE: str | None = "_reachy_robotis_locked_profile"
DEFAULT_PROFILES_DIRECTORY = Path(__file__).parent / "profiles"

logger = logging.getLogger(__name__)

# Realtime backend providers. The conversation app can talk to OpenAI Realtime
# directly (requires OPENAI_API_KEY) or to the Hugging Face realtime backend,
# which authenticates with the user's Hugging Face token and connects through a
# Pollen-managed session proxy (no OpenAI key required). HuggingFace is the
# default so the app works out of the box for Reachy Mini owners.
OPENAI_BACKEND = "openai"
HF_BACKEND = "huggingface"
DEFAULT_BACKEND_PROVIDER = HF_BACKEND
# App-managed Hugging Face Space proxy. It forwards to the current realtime
# session allocator, so allocator changes do not require app releases.
HF_REALTIME_SESSION_PROXY_URL = "https://pollen-robotics-reachy-mini-realtime-url.hf.space/session"


def _normalize_backend_provider(value: str | None) -> str:
    """Return a validated backend provider, defaulting to HuggingFace."""
    candidate = (value or "").strip().lower()
    if candidate in {OPENAI_BACKEND, HF_BACKEND}:
        return candidate
    if candidate:
        logger.warning(
            "Invalid BACKEND_PROVIDER=%r, expected one of %s. Using default %s.",
            value,
            (OPENAI_BACKEND, HF_BACKEND),
            DEFAULT_BACKEND_PROVIDER,
        )
    return DEFAULT_BACKEND_PROVIDER


@dataclass(frozen=True)
class HFRealtimeURLParts:
    """Parsed Hugging Face realtime URL components used for client setup."""

    base_url: str
    websocket_base_url: str
    connect_query: dict[str, str]


def parse_hf_realtime_url(realtime_url: str) -> HFRealtimeURLParts:
    """Parse a Hugging Face realtime URL into OpenAI-compatible client endpoints."""
    parsed = urlsplit(realtime_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"ws", "wss", "http", "https"}:
        raise ValueError(
            "Expected Hugging Face realtime URL to start with ws://, wss://, http://, or https://, "
            f"got: {realtime_url}"
        )

    path = parsed.path.rstrip("/")
    if path.endswith("/realtime"):
        base_path = path[: -len("/realtime")]
    else:
        base_path = path

    connect_query = {
        key: value
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "model"
    }
    http_scheme = "https" if scheme in {"wss", "https"} else "http"
    websocket_scheme = "wss" if scheme in {"wss", "https"} else "ws"
    base_url = urlunsplit((http_scheme, parsed.netloc, base_path, "", ""))
    websocket_base_url = urlunsplit((websocket_scheme, parsed.netloc, base_path, "", ""))
    return HFRealtimeURLParts(
        base_url=base_url,
        websocket_base_url=websocket_base_url,
        connect_query=connect_query,
    )


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment flag."""
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False

    logger.warning("Invalid boolean value for %s=%r, using default=%s", name, raw, default)
    return default


def _collect_profile_names(profiles_root: Path) -> set[str]:
    """Return profile folder names from a profiles root directory."""
    if not profiles_root.exists() or not profiles_root.is_dir():
        return set()
    return {p.name for p in profiles_root.iterdir() if p.is_dir()}


def _collect_tool_module_names(tools_root: Path) -> set[str]:
    """Return tool module names from a tools directory."""
    if not tools_root.exists() or not tools_root.is_dir():
        return set()
    ignored = {"__init__", "core_tools"}
    return {
        p.stem
        for p in tools_root.glob("*.py")
        if p.is_file() and p.stem not in ignored
    }


def _raise_on_name_collisions(
    *,
    label: str,
    external_root: Path,
    internal_root: Path,
    external_names: set[str],
    internal_names: set[str],
) -> None:
    """Raise with a clear message when external/internal names collide."""
    collisions = sorted(external_names & internal_names)
    if not collisions:
        return

    raise RuntimeError(
        f"Config.__init__(): Ambiguous {label} names found in both external and built-in libraries: {collisions}. "
        f"External {label} root: {external_root}. Built-in {label} root: {internal_root}. "
        f"Please rename the conflicting external {label}(s) to continue."
    )


if LOCKED_PROFILE is not None:
    _profiles_dir = DEFAULT_PROFILES_DIRECTORY
    _profile_path = _profiles_dir / LOCKED_PROFILE
    _instructions_file = _profile_path / "instructions.txt"
    if not _profile_path.is_dir():
        print(f"Error: LOCKED_PROFILE '{LOCKED_PROFILE}' does not exist in {_profiles_dir}", file=sys.stderr)
        sys.exit(1)
    if not _instructions_file.is_file():
        print(f"Error: LOCKED_PROFILE '{LOCKED_PROFILE}' has no instructions.txt", file=sys.stderr)
        sys.exit(1)

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT_ENV_PATH = PROJECT_ROOT_DIR / ".env"
LEGACY_PACKAGE_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _migrate_legacy_env() -> None:
    """Move a stray ``src/reachy_robotis/.env`` to the project root once."""
    if not LEGACY_PACKAGE_ENV_PATH.exists():
        return
    if PROJECT_ROOT_ENV_PATH.exists():
        logger.warning(
            "Ignoring legacy %s; project root .env takes precedence. "
            "Delete the legacy file to silence this warning.",
            LEGACY_PACKAGE_ENV_PATH,
        )
        return
    try:
        import shutil

        shutil.move(str(LEGACY_PACKAGE_ENV_PATH), str(PROJECT_ROOT_ENV_PATH))
        logger.warning(
            "Migrated legacy package .env to project root: %s -> %s. "
            "If this file ever held an API key that appeared in logs, REVOKE that key.",
            LEGACY_PACKAGE_ENV_PATH,
            PROJECT_ROOT_ENV_PATH,
        )
    except Exception as exc:
        logger.warning("Failed to migrate legacy package .env: %s", exc)


_skip_dotenv = _env_flag("REACHY_MINI_SKIP_DOTENV", default=False)

if _skip_dotenv:
    logger.info("Skipping .env loading because REACHY_MINI_SKIP_DOTENV is set")
else:
    _migrate_legacy_env()

    if PROJECT_ROOT_ENV_PATH.exists():
        load_dotenv(dotenv_path=str(PROJECT_ROOT_ENV_PATH), override=True)
        logger.info("Configuration loaded from %s", PROJECT_ROOT_ENV_PATH)
    elif LEGACY_PACKAGE_ENV_PATH.exists():
        load_dotenv(dotenv_path=str(LEGACY_PACKAGE_ENV_PATH), override=True)
        logger.warning(
            "Loaded API config from legacy %s. Move it to %s.",
            LEGACY_PACKAGE_ENV_PATH,
            PROJECT_ROOT_ENV_PATH,
        )
    else:
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=True)
            logger.info("Configuration loaded from %s", dotenv_path)
        else:
            logger.warning("No .env file found, using environment variables")


class Config:
    """Configuration class for the conversation app."""

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Realtime backend selection. Defaults to HuggingFace (HF token auth, no
    # OpenAI key needed). Set BACKEND_PROVIDER=openai to use OpenAI Realtime.
    BACKEND_PROVIDER = _normalize_backend_provider(os.getenv("BACKEND_PROVIDER"))

    # The HuggingFace endpoint selects its own realtime model, so MODEL_NAME is
    # empty for the HF backend; OpenAI keeps a concrete realtime model id.
    if BACKEND_PROVIDER == HF_BACKEND:
        MODEL_NAME = os.getenv("MODEL_NAME", "")
    else:
        MODEL_NAME = os.getenv("MODEL_NAME", "gpt-realtime")

    HF_REALTIME_SESSION_URL = HF_REALTIME_SESSION_PROXY_URL
    HF_HOME = os.getenv("HF_HOME", "./cache")
    LOCAL_VISION_MODEL = os.getenv("LOCAL_VISION_MODEL", "HuggingFaceTB/SmolVLM2-2.2B-Instruct")
    HF_TOKEN = os.getenv("HF_TOKEN")

    logger.debug(f"Model: {MODEL_NAME}, HF_HOME: {HF_HOME}, Vision Model: {LOCAL_VISION_MODEL}")

    _profiles_directory_env = os.getenv("REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY")
    PROFILES_DIRECTORY = (
        Path(_profiles_directory_env) if _profiles_directory_env else Path(__file__).parent / "profiles"
    )
    _tools_directory_env = os.getenv("REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY")
    TOOLS_DIRECTORY = Path(_tools_directory_env) if _tools_directory_env else None
    AUTOLOAD_EXTERNAL_TOOLS = _env_flag("AUTOLOAD_EXTERNAL_TOOLS", default=False)
    REACHY_MINI_CUSTOM_PROFILE = LOCKED_PROFILE or os.getenv("REACHY_MINI_CUSTOM_PROFILE")

    logger.debug(f"Custom Profile: {REACHY_MINI_CUSTOM_PROFILE}")

    def __init__(self) -> None:
        """Initialize the configuration."""
        if self.REACHY_MINI_CUSTOM_PROFILE and self.PROFILES_DIRECTORY != DEFAULT_PROFILES_DIRECTORY:
            selected_profile_path = self.PROFILES_DIRECTORY / self.REACHY_MINI_CUSTOM_PROFILE
            if not selected_profile_path.is_dir():
                available_profiles = sorted(_collect_profile_names(self.PROFILES_DIRECTORY))
                raise RuntimeError(
                    "Config.__init__(): Selected profile "
                    f"'{self.REACHY_MINI_CUSTOM_PROFILE}' was not found in external profiles root "
                    f"{self.PROFILES_DIRECTORY}. "
                    f"Available external profiles: {available_profiles}. "
                    "Either set 'REACHY_MINI_CUSTOM_PROFILE' to one of the available external profiles "
                    "or unset 'REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY' to use built-in profiles."
                )

        if self.PROFILES_DIRECTORY != DEFAULT_PROFILES_DIRECTORY:
            external_profiles = _collect_profile_names(self.PROFILES_DIRECTORY)
            internal_profiles = _collect_profile_names(DEFAULT_PROFILES_DIRECTORY)
            _raise_on_name_collisions(
                label="profile",
                external_root=self.PROFILES_DIRECTORY,
                internal_root=DEFAULT_PROFILES_DIRECTORY,
                external_names=external_profiles,
                internal_names=internal_profiles,
            )

        if self.TOOLS_DIRECTORY is not None:
            builtin_tools_root = Path(__file__).parent / "tools"
            external_tools = _collect_tool_module_names(self.TOOLS_DIRECTORY)
            internal_tools = _collect_tool_module_names(builtin_tools_root)
            _raise_on_name_collisions(
                label="tool",
                external_root=self.TOOLS_DIRECTORY,
                internal_root=builtin_tools_root,
                external_names=external_tools,
                internal_names=internal_tools,
            )

        if self.PROFILES_DIRECTORY != DEFAULT_PROFILES_DIRECTORY:
            logger.warning(
                "Environment variable 'REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY' is set. "
                "Profiles (instructions.txt, ...) will be loaded from %s.",
                self.PROFILES_DIRECTORY,
            )
        else:
            logger.info(
                "'REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY' is not set. "
                "Using built-in profiles from %s.",
                DEFAULT_PROFILES_DIRECTORY,
            )

        if self.TOOLS_DIRECTORY is not None:
            logger.warning(
                "Environment variable 'REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY' is set. "
                "External tools will be loaded from %s.",
                self.TOOLS_DIRECTORY,
            )
        else:
            logger.info(
                "'REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY' is not set. "
                "Using built-in shared tools only."
            )


config = Config()


def resolve_env_path() -> Path:
    """Return the canonical ``.env`` path used for persisting settings."""
    return PROJECT_ROOT_ENV_PATH


def get_hf_token() -> str | None:
    """Return the Hugging Face token from config/env, falling back to the CLI login.

    Reachy Mini owners are logged in via ``hf auth login``; ``huggingface_hub``
    exposes that token even when ``HF_TOKEN`` is not set in the environment.
    """
    token = (config.HF_TOKEN or "").strip()
    if token:
        return token
    try:
        import huggingface_hub as hf

        cli_token = (hf.get_token() or "").strip()
        return cli_token or None
    except Exception:
        return None


def set_custom_profile(profile: str | None) -> None:
    """Update the selected custom profile at runtime and expose it via env."""
    if LOCKED_PROFILE is not None:
        return
    try:
        config.REACHY_MINI_CUSTOM_PROFILE = profile
    except Exception:
        pass
    try:
        import os as _os

        if profile:
            _os.environ["REACHY_MINI_CUSTOM_PROFILE"] = profile
        else:
            _os.environ.pop("REACHY_MINI_CUSTOM_PROFILE", None)
    except Exception:
        pass
