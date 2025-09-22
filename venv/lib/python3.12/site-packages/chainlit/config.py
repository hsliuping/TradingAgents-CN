import json
import os
import site
import sys
from importlib import util
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Union,
)

import tomli
from dataclasses_json import DataClassJsonMixin
from pydantic import Field
from pydantic.dataclasses import dataclass
from starlette.datastructures import Headers

from chainlit.data.base import BaseDataLayer
from chainlit.logger import logger
from chainlit.translations import lint_translation_json
from chainlit.version import __version__

from ._utils import is_path_inside

if TYPE_CHECKING:
    from fastapi import Request, Response

    from chainlit.action import Action
    from chainlit.message import Message
    from chainlit.types import (
        ChatProfile,
        Feedback,
        InputAudioChunk,
        Starter,
        ThreadDict,
    )
    from chainlit.user import User
else:
    # Pydantic needs to resolve forward annotations. Because all of these are used
    # within `typing.Callable`, alias to `Any` as Pydantic does not perform validation
    # of callable argument/return types anyway.
    Request = Response = Action = Message = ChatProfile = InputAudioChunk = Starter = ThreadDict = User = Feedback = Any  # fmt: off

BACKEND_ROOT = os.path.dirname(__file__)
PACKAGE_ROOT = os.path.dirname(os.path.dirname(BACKEND_ROOT))
TRANSLATIONS_DIR = os.path.join(BACKEND_ROOT, "translations")


# Get the directory the script is running from
APP_ROOT = os.getenv("CHAINLIT_APP_ROOT", os.getcwd())

# Create the directory to store the uploaded files
FILES_DIRECTORY = Path(APP_ROOT) / ".files"
FILES_DIRECTORY.mkdir(exist_ok=True)

config_dir = os.path.join(APP_ROOT, ".chainlit")
public_dir = os.path.join(APP_ROOT, "public")
config_file = os.path.join(config_dir, "config.toml")
config_translation_dir = os.path.join(config_dir, "translations")

# Default config file created if none exists
DEFAULT_CONFIG_STR = f"""[project]
# List of environment variables to be provided by each user to use the app.
user_env = []

# Duration (in seconds) during which the session is saved when the connection is lost
session_timeout = 3600

# Duration (in seconds) of the user session expiry
user_session_timeout = 1296000  # 15 days

# Enable third parties caching (e.g., LangChain cache)
cache = false

# Authorized origins
allow_origins = ["*"]

[features]
# Process and display HTML in messages. This can be a security risk (see https://stackoverflow.com/questions/19603097/why-is-it-dangerous-to-render-user-generated-html-or-javascript)
unsafe_allow_html = false

# Process and display mathematical expressions. This can clash with "$" characters in messages.
latex = false

# Autoscroll new user messages at the top of the window
user_message_autoscroll = true

# Automatically tag threads with the current chat profile (if a chat profile is used)
auto_tag_thread = true

# Allow users to edit their own messages
edit_message = true

# Authorize users to spontaneously upload files with messages
[features.spontaneous_file_upload]
    enabled = true
    # Define accepted file types using MIME types
    # Examples:
    # 1. For specific file types:
    #    accept = ["image/jpeg", "image/png", "application/pdf"]
    # 2. For all files of certain type:
    #    accept = ["image/*", "audio/*", "video/*"]
    # 3. For specific file extensions:
    #    accept = {{ "application/octet-stream" = [".xyz", ".pdb"] }}
    # Note: Using "*/*" is not recommended as it may cause browser warnings
    accept = ["*/*"]
    max_files = 20
    max_size_mb = 500

[features.audio]
    # Sample rate of the audio
    sample_rate = 24000

[features.mcp.sse]
    enabled = true

[features.mcp.stdio]
    enabled = true
    # Only the executables in the allow list can be used for MCP stdio server.
    # Only need the base name of the executable, e.g. "npx", not "/usr/bin/npx".
    # Please don't comment this line for now, we need it to parse the executable name.
    allowed_executables = [ "npx", "uvx" ]

[UI]
# Name of the assistant.
name = "Assistant"

# default_theme = "dark"

# layout = "wide"

# default_sidebar_state = "open"

# Description of the assistant. This is used for HTML tags.
# description = ""

# Chain of Thought (CoT) display mode. Can be "hidden", "tool_call" or "full".
cot = "full"

# Specify a CSS file that can be used to customize the user interface.
# The CSS file can be served from the public directory or via an external link.
# custom_css = "/public/test.css"

# Specify additional attributes for a custom CSS file
# custom_css_attributes = "media=\\\"print\\\""

# Specify a JavaScript file that can be used to customize the user interface.
# The JavaScript file can be served from the public directory.
# custom_js = "/public/test.js"

# The style of alert boxes. Can be "classic" or "modern".
alert_style = "classic"

# Specify additional attributes for custom JS file
# custom_js_attributes = "async type = \\\"module\\\""

# Custom login page image, relative to public directory or external URL
# login_page_image = "/public/custom-background.jpg"

# Custom login page image filter (Tailwind internal filters, no dark/light variants)
# login_page_image_filter = "brightness-50 grayscale"
# login_page_image_dark_filter = "contrast-200 blur-sm"


# Specify a custom meta image url.
# custom_meta_image_url = "https://chainlit-cloud.s3.eu-west-3.amazonaws.com/logo/chainlit_banner.png"

# Load assistant logo directly from URL.
logo_file_url = ""

# Load assistant avatar image directly from URL.
default_avatar_file_url = ""

# Specify a custom build directory for the frontend.
# This can be used to customize the frontend code.
# Be careful: If this is a relative path, it should not start with a slash.
# custom_build = "./public/build"

# Specify optional one or more custom links in the header.
# [[UI.header_links]]
#     name = "Issues"
#     display_name = "Report Issue"
#     icon_url = "https://avatars.githubusercontent.com/u/128686189?s=200&v=4"
#     url = "https://github.com/Chainlit/chainlit/issues"

[meta]
generated_by = "{__version__}"
"""


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_ROOT_PATH = ""


@dataclass()
class RunSettings:
    # Name of the module (python file) used in the run command
    module_name: Optional[str] = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    root_path: str = DEFAULT_ROOT_PATH
    headless: bool = False
    watch: bool = False
    no_cache: bool = False
    debug: bool = False
    ci: bool = False


@dataclass()
class PaletteOptions(DataClassJsonMixin):
    main: Optional[str] = ""
    light: Optional[str] = ""
    dark: Optional[str] = ""


@dataclass()
class TextOptions(DataClassJsonMixin):
    primary: Optional[str] = ""
    secondary: Optional[str] = ""


@dataclass()
class Palette(DataClassJsonMixin):
    primary: Optional[PaletteOptions] = None
    background: Optional[str] = ""
    paper: Optional[str] = ""
    text: Optional[TextOptions] = None


@dataclass
class SpontaneousFileUploadFeature(DataClassJsonMixin):
    enabled: Optional[bool] = None
    accept: Optional[Union[List[str], Dict[str, List[str]]]] = None
    max_files: Optional[int] = None
    max_size_mb: Optional[int] = None


@dataclass
class AudioFeature(DataClassJsonMixin):
    sample_rate: int = 24000
    enabled: bool = False


@dataclass
class McpSseFeature(DataClassJsonMixin):
    enabled: bool = True


@dataclass
class McpStdioFeature(DataClassJsonMixin):
    enabled: bool = True
    allowed_executables: Optional[list[str]] = None


@dataclass
class McpFeature(DataClassJsonMixin):
    enabled: bool = False
    sse: McpSseFeature = Field(default_factory=McpSseFeature)
    stdio: McpStdioFeature = Field(default_factory=McpStdioFeature)


@dataclass()
class FeaturesSettings(DataClassJsonMixin):
    spontaneous_file_upload: Optional[SpontaneousFileUploadFeature] = None
    audio: Optional[AudioFeature] = Field(default_factory=AudioFeature)
    mcp: McpFeature = Field(default_factory=McpFeature)
    latex: bool = False
    user_message_autoscroll: bool = True
    unsafe_allow_html: bool = False
    auto_tag_thread: bool = True
    edit_message: bool = True


@dataclass
class HeaderLink(DataClassJsonMixin):
    name: str
    icon_url: str
    url: str
    display_name: Optional[str] = None


@dataclass()
class UISettings(DataClassJsonMixin):
    name: str
    description: str = ""
    cot: Literal["hidden", "tool_call", "full"] = "full"
    font_family: Optional[str] = None
    default_theme: Optional[Literal["light", "dark"]] = "dark"
    layout: Optional[Literal["default", "wide"]] = "default"
    default_sidebar_state: Optional[Literal["open", "closed"]] = "open"
    github: Optional[str] = None
    # Optional custom CSS file that allows you to customize the UI
    custom_css: Optional[str] = None
    custom_css_attributes: Optional[str] = ""
    # Optional custom JS file that allows you to customize the UI
    custom_js: Optional[str] = None

    alert_style: Optional[Literal["classic", "modern"]] = "classic"
    custom_js_attributes: Optional[str] = "defer"
    # Optional custom background image for login page
    login_page_image: Optional[str] = None
    login_page_image_filter: Optional[str] = None
    login_page_image_dark_filter: Optional[str] = None

    # Optional custom meta tag for image preview
    custom_meta_image_url: Optional[str] = None
    # Optional logo file url
    logo_file_url: Optional[str] = None
    # Optional avatar image file url
    default_avatar_file_url: Optional[str] = None
    # Optional custom build directory for the frontend
    custom_build: Optional[str] = None
    # Optional header links
    header_links: Optional[List[HeaderLink]] = None


@dataclass()
class CodeSettings:
    # App action functions
    action_callbacks: Dict[str, Callable[["Action"], Any]]

    # Module object loaded from the module_name
    module: Any = None

    # App life cycle callbacks
    on_app_startup: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
    on_app_shutdown: Optional[Callable[[], Union[None, Awaitable[None]]]] = None

    # Session life cycle callbacks
    on_logout: Optional[Callable[["Request", "Response"], Any]] = None
    on_stop: Optional[Callable[[], Any]] = None
    on_chat_start: Optional[Callable[[], Any]] = None
    on_chat_end: Optional[Callable[[], Any]] = None
    on_chat_resume: Optional[Callable[["ThreadDict"], Any]] = None
    on_message: Optional[Callable[["Message"], Any]] = None
    on_feedback: Optional[Callable[["Feedback"], Any]] = None
    on_audio_start: Optional[Callable[[], Any]] = None
    on_audio_chunk: Optional[Callable[["InputAudioChunk"], Any]] = None
    on_audio_end: Optional[Callable[[], Any]] = None
    on_mcp_connect: Optional[Callable] = None
    on_mcp_disconnect: Optional[Callable] = None
    on_settings_update: Optional[Callable[[Dict[str, Any]], Any]] = None
    set_chat_profiles: Optional[
        Callable[[Optional["User"]], Awaitable[List["ChatProfile"]]]
    ] = None
    set_starters: Optional[Callable[[Optional["User"]], Awaitable[List["Starter"]]]] = (
        None
    )
    # Auth callbacks
    password_auth_callback: Optional[
        Callable[[str, str], Awaitable[Optional["User"]]]
    ] = None
    header_auth_callback: Optional[Callable[[Headers], Awaitable[Optional["User"]]]] = (
        None
    )
    oauth_callback: Optional[
        Callable[[str, str, Dict[str, str], "User"], Awaitable[Optional["User"]]]
    ] = None

    # Helpers
    on_window_message: Optional[Callable[[str], Any]] = None
    author_rename: Optional[Callable[[str], Awaitable[str]]] = None
    data_layer: Optional[Callable[[], BaseDataLayer]] = None


@dataclass()
class ProjectSettings(DataClassJsonMixin):
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    # Socket.io client transports option
    transports: Optional[List[str]] = None
    # List of environment variables to be provided by each user to use the app. If empty, no environment variables will be asked to the user.
    user_env: Optional[List[str]] = None
    # Path to the local langchain cache database
    lc_cache_path: Optional[str] = None
    # Path to the local chat db
    # Duration (in seconds) during which the session is saved when the connection is lost
    session_timeout: int = 300
    # Duration (in seconds) of the user session expiry
    user_session_timeout: int = 1296000  # 15 days
    # Enable third parties caching (e.g LangChain cache)
    cache: bool = False


@dataclass()
class ChainlitConfig:
    # Directory where the Chainlit project is located
    root = APP_ROOT
    # Chainlit server URL. Used only for cloud features
    chainlit_server: str
    run: RunSettings
    features: FeaturesSettings
    ui: UISettings
    project: ProjectSettings
    code: CodeSettings

    def load_translation(self, language: str):
        translation = {}
        default_language = "en-US"
        # fallback to root language (ex: `de` when `de-DE` is not found)
        parent_language = language.split("-")[0]

        translation_dir = Path(config_translation_dir)

        translation_lib_file_path = translation_dir / f"{language}.json"
        translation_lib_parent_language_file_path = (
            translation_dir / f"{parent_language}.json"
        )
        default_translation_lib_file_path = translation_dir / f"{default_language}.json"

        if (
            is_path_inside(translation_lib_file_path, translation_dir)
            and translation_lib_file_path.is_file()
        ):
            translation = json.loads(
                translation_lib_file_path.read_text(encoding="utf-8")
            )
        elif (
            is_path_inside(translation_lib_parent_language_file_path, translation_dir)
            and translation_lib_parent_language_file_path.is_file()
        ):
            logger.warning(
                f"Translation file for {language} not found. Using parent translation {parent_language}."
            )
            translation = json.loads(
                translation_lib_parent_language_file_path.read_text(encoding="utf-8")
            )
        elif (
            is_path_inside(default_translation_lib_file_path, translation_dir)
            and default_translation_lib_file_path.is_file()
        ):
            logger.warning(
                f"Translation file for {language} not found. Using default translation {default_language}."
            )
            translation = json.loads(
                default_translation_lib_file_path.read_text(encoding="utf-8")
            )

        return translation


def init_config(log=False):
    """Initialize the configuration file if it doesn't exist."""
    if not os.path.exists(config_file):
        os.makedirs(config_dir, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_STR)
            logger.info(f"Created default config file at {config_file}")
    elif log:
        logger.info(f"Config file already exists at {config_file}")

    if not os.path.exists(config_translation_dir):
        os.makedirs(config_translation_dir, exist_ok=True)
        logger.info(
            f"Created default translation directory at {config_translation_dir}"
        )

    for file in os.listdir(TRANSLATIONS_DIR):
        if file.endswith(".json"):
            dst = os.path.join(config_translation_dir, file)
            if not os.path.exists(dst):
                src = os.path.join(TRANSLATIONS_DIR, file)
                with open(src, encoding="utf-8") as f:
                    translation = json.load(f)
                    with open(dst, "w", encoding="utf-8") as f:
                        json.dump(translation, f, indent=4)
                        logger.info(f"Created default translation file at {dst}")


def load_module(target: str, force_refresh: bool = False):
    """Load the specified module."""

    # Get the target's directory
    target_dir = os.path.dirname(os.path.abspath(target))

    # Add the target's directory to the Python path
    sys.path.insert(0, target_dir)

    if force_refresh:
        # Get current site packages dirs
        site_package_dirs = site.getsitepackages()

        # Clear the modules related to the app from sys.modules
        for module_name, module in list(sys.modules.items()):
            if (
                hasattr(module, "__file__")
                and module.__file__
                and module.__file__.startswith(target_dir)
                and not any(module.__file__.startswith(p) for p in site_package_dirs)
            ):
                sys.modules.pop(module_name, None)

    spec = util.spec_from_file_location(target, target)
    if not spec or not spec.loader:
        return

    module = util.module_from_spec(spec)
    if not module:
        return

    spec.loader.exec_module(module)

    sys.modules[target] = module

    # Remove the target's directory from the Python path
    sys.path.pop(0)


def load_settings():
    with open(config_file, "rb") as f:
        toml_dict = tomli.load(f)
        # Load project settings
        project_config = toml_dict.get("project", {})
        features_settings = toml_dict.get("features", {})
        ui_settings = toml_dict.get("UI", {})
        meta = toml_dict.get("meta")

        if not meta or meta.get("generated_by") <= "0.3.0":
            raise ValueError(
                f"Your config file '{config_file}' is outdated. Please delete it and restart the app to regenerate it."
            )

        lc_cache_path = os.path.join(config_dir, ".langchain.db")

        project_settings = ProjectSettings(
            lc_cache_path=lc_cache_path,
            **project_config,
        )

        features_settings = FeaturesSettings(**features_settings)

        ui_settings = UISettings(**ui_settings)

        code_settings = CodeSettings(action_callbacks={})

        return {
            "features": features_settings,
            "ui": ui_settings,
            "project": project_settings,
            "code": code_settings,
        }


def reload_config():
    """Reload the configuration from the config file."""
    global config
    if config is None:
        return

    settings = load_settings()

    config.features = settings["features"]
    config.code = settings["code"]
    config.ui = settings["ui"]
    config.project = settings["project"]


def load_config():
    """Load the configuration from the config file."""
    init_config()

    settings = load_settings()

    chainlit_server = os.environ.get("CHAINLIT_SERVER", "https://cloud.chainlit.io")

    config = ChainlitConfig(
        chainlit_server=chainlit_server,
        run=RunSettings(),
        **settings,
    )

    return config


def lint_translations():
    # Load the ground truth (en-US.json file from chainlit source code)
    src = os.path.join(TRANSLATIONS_DIR, "en-US.json")
    with open(src, encoding="utf-8") as f:
        truth = json.load(f)

        # Find the local app translations
        for file in os.listdir(config_translation_dir):
            if file.endswith(".json"):
                # Load the translation file
                to_lint = os.path.join(config_translation_dir, file)
                with open(to_lint, encoding="utf-8") as f:
                    translation = json.load(f)

                    # Lint the translation file
                    lint_translation_json(file, truth, translation)


config = load_config()
