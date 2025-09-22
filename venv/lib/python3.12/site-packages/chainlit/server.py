import asyncio
import fnmatch
import glob
import json
import mimetypes
import os
import re
import shutil
import urllib.parse
import webbrowser
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import List, Optional, Union, cast

import socketio
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from starlette.datastructures import URL
from starlette.middleware.cors import CORSMiddleware
from typing_extensions import Annotated
from watchfiles import awatch

from chainlit.auth import create_jwt, decode_jwt, get_configuration, get_current_user
from chainlit.auth.cookie import (
    clear_auth_cookie,
    clear_oauth_state_cookie,
    set_auth_cookie,
    set_oauth_state_cookie,
    validate_oauth_state_cookie,
)
from chainlit.config import (
    APP_ROOT,
    BACKEND_ROOT,
    DEFAULT_HOST,
    FILES_DIRECTORY,
    PACKAGE_ROOT,
    config,
    load_module,
    public_dir,
    reload_config,
)
from chainlit.data import get_data_layer
from chainlit.data.acl import is_thread_author
from chainlit.logger import logger
from chainlit.markdown import get_markdown_str
from chainlit.oauth_providers import get_oauth_provider
from chainlit.secret import random_secret
from chainlit.types import (
    CallActionRequest,
    ConnectMCPRequest,
    DeleteFeedbackRequest,
    DeleteThreadRequest,
    DisconnectMCPRequest,
    ElementRequest,
    GetThreadsRequest,
    Theme,
    UpdateFeedbackRequest,
    UpdateThreadRequest,
)
from chainlit.user import PersistedUser, User

from ._utils import is_path_inside

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager to handle app start and shutdown."""
    if config.code.on_app_startup:
        await config.code.on_app_startup()

    host = config.run.host
    port = config.run.port
    root_path = os.getenv("CHAINLIT_ROOT_PATH", "")

    if host == DEFAULT_HOST:
        url = f"http://localhost:{port}{root_path}"
    else:
        url = f"http://{host}:{port}{root_path}"

    logger.info(f"Your app is available at {url}")

    if not config.run.headless:
        # Add a delay before opening the browser
        await asyncio.sleep(1)
        webbrowser.open(url)

    watch_task = None
    stop_event = asyncio.Event()

    if config.run.watch:

        async def watch_files_for_changes():
            extensions = [".py"]
            files = ["chainlit.md", "config.toml"]
            async for changes in awatch(config.root, stop_event=stop_event):
                for change_type, file_path in changes:
                    file_name = os.path.basename(file_path)
                    file_ext = os.path.splitext(file_name)[1]

                    if file_ext.lower() in extensions or file_name.lower() in files:
                        logger.info(
                            f"File {change_type.name}: {file_name}. Reloading app..."
                        )

                        try:
                            reload_config()
                        except Exception as e:
                            logger.error(f"Error reloading config: {e}")
                            break

                        # Reload the module if the module name is specified in the config
                        if config.run.module_name:
                            try:
                                load_module(config.run.module_name, force_refresh=True)
                            except Exception as e:
                                logger.error(f"Error reloading module: {e}")

                        await asyncio.sleep(1)
                        await sio.emit("reload", {})

                        break

        watch_task = asyncio.create_task(watch_files_for_changes())

    discord_task = None

    if discord_bot_token := os.environ.get("DISCORD_BOT_TOKEN"):
        from chainlit.discord.app import client

        discord_task = asyncio.create_task(client.start(discord_bot_token))

    try:
        yield
    finally:
        try:
            if config.code.on_app_shutdown:
                await config.code.on_app_shutdown()

            if watch_task:
                stop_event.set()
                watch_task.cancel()
                await watch_task

            if discord_task:
                discord_task.cancel()
                await discord_task
        except asyncio.exceptions.CancelledError:
            pass

        if FILES_DIRECTORY.is_dir():
            shutil.rmtree(FILES_DIRECTORY)

        # Force exit the process to avoid potential AnyIO threads still running
        os._exit(0)


def get_build_dir(local_target: str, packaged_target: str) -> str:
    """
    Get the build directory based on the UI build strategy.

    Args:
        local_target (str): The local target directory.
        packaged_target (str): The packaged target directory.

    Returns:
        str: The build directory
    """

    local_build_dir = os.path.join(PACKAGE_ROOT, local_target, "dist")
    packaged_build_dir = os.path.join(BACKEND_ROOT, packaged_target, "dist")

    if config.ui.custom_build and os.path.exists(
        os.path.join(APP_ROOT, config.ui.custom_build)
    ):
        return os.path.join(APP_ROOT, config.ui.custom_build)
    elif os.path.exists(local_build_dir):
        return local_build_dir
    elif os.path.exists(packaged_build_dir):
        return packaged_build_dir
    else:
        raise FileNotFoundError(f"{local_target} built UI dir not found")


build_dir = get_build_dir("frontend", "frontend")
copilot_build_dir = get_build_dir(os.path.join("libs", "copilot"), "copilot")

app = FastAPI(lifespan=lifespan)

sio = socketio.AsyncServer(cors_allowed_origins=[], async_mode="asgi")

asgi_app = socketio.ASGIApp(socketio_server=sio, socketio_path="")

# config.run.root_path is only set when started with --root-path. Not on submounts.
app.mount(f"{config.run.root_path}/ws/socket.io", asgi_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.project.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# config.run.root_path is only set when started with --root-path. Not on submounts.
router = APIRouter(prefix=config.run.root_path)


@router.get("/public/{filename:path}")
async def serve_public_file(
    filename: str,
):
    """Serve a file from public dir."""

    base_path = Path(public_dir)
    file_path = (base_path / filename).resolve()

    if not is_path_inside(file_path, base_path):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if file_path.is_file():
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/assets/{filename:path}")
async def serve_asset_file(
    filename: str,
):
    """Serve a file from assets dir."""

    base_path = Path(os.path.join(build_dir, "assets"))
    file_path = (base_path / filename).resolve()

    if not is_path_inside(file_path, base_path):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if file_path.is_file():
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/copilot/{filename:path}")
async def serve_copilot_file(
    filename: str,
):
    """Serve a file from assets dir."""

    base_path = Path(copilot_build_dir)
    file_path = (base_path / filename).resolve()

    if not is_path_inside(file_path, base_path):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if file_path.is_file():
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


# -------------------------------------------------------------------------------
#                               SLACK HANDLER
# -------------------------------------------------------------------------------

if os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_SIGNING_SECRET"):
    from chainlit.slack.app import slack_app_handler

    @router.post("/slack/events")
    async def slack_endpoint(req: Request):
        return await slack_app_handler.handle(req)


# -------------------------------------------------------------------------------
#                               TEAMS HANDLER
# -------------------------------------------------------------------------------

if os.environ.get("TEAMS_APP_ID") and os.environ.get("TEAMS_APP_PASSWORD"):
    from botbuilder.schema import Activity

    from chainlit.teams.app import adapter, bot

    @router.post("/teams/events")
    async def teams_endpoint(req: Request):
        body = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        return response


# -------------------------------------------------------------------------------
#                               HTTP HANDLERS
# -------------------------------------------------------------------------------


def replace_between_tags(
    text: str, start_tag: str, end_tag: str, replacement: str
) -> str:
    """Replace text between two tags in a string."""

    pattern = start_tag + ".*?" + end_tag
    return re.sub(pattern, start_tag + replacement + end_tag, text, flags=re.DOTALL)


def get_html_template(root_path):
    """
    Get HTML template for the index view.
    """
    root_path = root_path.rstrip("/")  # Avoid duplicated / when joining with root path.

    custom_theme = None
    custom_theme_file_path = Path(public_dir) / "theme.json"
    if (
        is_path_inside(custom_theme_file_path, Path(public_dir))
        and custom_theme_file_path.is_file()
    ):
        custom_theme = json.loads(custom_theme_file_path.read_text(encoding="utf-8"))

    PLACEHOLDER = "<!-- TAG INJECTION PLACEHOLDER -->"
    JS_PLACEHOLDER = "<!-- JS INJECTION PLACEHOLDER -->"
    CSS_PLACEHOLDER = "<!-- CSS INJECTION PLACEHOLDER -->"

    default_url = "https://github.com/Chainlit/chainlit"
    default_meta_image_url = (
        "https://chainlit-cloud.s3.eu-west-3.amazonaws.com/logo/chainlit_banner.png"
    )
    meta_image_url = config.ui.custom_meta_image_url or default_meta_image_url
    favicon_path = "/favicon"

    tags = f"""<title>{config.ui.name}</title>
    <link rel="icon" href="{favicon_path}" />
    <meta name="description" content="{config.ui.description}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{config.ui.name}">
    <meta property="og:description" content="{config.ui.description}">
    <meta property="og:image" content="{meta_image_url}">
    <meta property="og:url" content="{default_url}">
    <meta property="og:root_path" content="{root_path}">"""

    js = f"""<script>
{f"window.theme = {json.dumps(custom_theme.get('variables'))};" if custom_theme and custom_theme.get("variables") else "undefined"}
{f"window.transports = {json.dumps(config.project.transports)};" if config.project.transports else "undefined"}
</script>"""

    css = None
    if config.ui.custom_css:
        css = f"""<link rel="stylesheet" type="text/css" href="{config.ui.custom_css}" {config.ui.custom_css_attributes}>"""

    if config.ui.custom_js:
        js += f"""<script src="{config.ui.custom_js}" {config.ui.custom_js_attributes}></script>"""

    font = None
    if custom_theme and custom_theme.get("custom_fonts"):
        font = "\n".join(
            f"""<link rel="stylesheet" href="{font}">"""
            for font in custom_theme.get("custom_fonts")
        )

    index_html_file_path = os.path.join(build_dir, "index.html")

    with open(index_html_file_path, encoding="utf-8") as f:
        content = f.read()
        content = content.replace(PLACEHOLDER, tags)
        if js:
            content = content.replace(JS_PLACEHOLDER, js)
        if css:
            content = content.replace(CSS_PLACEHOLDER, css)
        if font:
            content = replace_between_tags(
                content, "<!-- FONT START -->", "<!-- FONT END -->", font
            )
        content = content.replace('href="/', f'href="{root_path}/')
        content = content.replace('src="/', f'src="{root_path}/')
        return content


def get_user_facing_url(url: URL):
    """
    Return the user facing URL for a given URL.
    Handles deployment with proxies (like cloud run).
    """
    chainlit_url = os.environ.get("CHAINLIT_URL")

    # No config, we keep the URL as is
    if not chainlit_url:
        url = url.replace(query="", fragment="")
        return url.__str__()

    config_url = URL(chainlit_url).replace(
        query="",
        fragment="",
    )
    # Remove trailing slash from config URL
    if config_url.path.endswith("/"):
        config_url = config_url.replace(path=config_url.path[:-1])

    return config_url.__str__() + url.path


@router.get("/auth/config")
async def auth(request: Request):
    return get_configuration()


def _get_response_dict(access_token: str) -> dict:
    """Get the response dictionary for the auth response."""

    return {"success": True}


def _get_auth_response(access_token: str, redirect_to_callback: bool) -> Response:
    """Get the redirect params for the OAuth callback."""

    response_dict = _get_response_dict(access_token)

    if redirect_to_callback:
        root_path = os.environ.get("CHAINLIT_ROOT_PATH", "")
        root_path = "" if root_path == "/" else root_path
        redirect_url = (
            f"{root_path}/login/callback?{urllib.parse.urlencode(response_dict)}"
        )

        return RedirectResponse(
            # FIXME: redirect to the right frontend base url to improve the dev environment
            url=redirect_url,
            status_code=302,
        )

    return JSONResponse(response_dict)


def _get_oauth_redirect_error(request: Request, error: str) -> Response:
    """Get the redirect response for an OAuth error."""
    params = urllib.parse.urlencode(
        {
            "error": error,
        }
    )
    response = RedirectResponse(url=str(request.url_for("login")) + "?" + params)
    return response


async def _authenticate_user(
    request: Request, user: Optional[User], redirect_to_callback: bool = False
) -> Response:
    """Authenticate a user and return the response."""

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credentialssignin",
        )

    # If a data layer is defined, attempt to persist user.
    if data_layer := get_data_layer():
        try:
            await data_layer.create_user(user)
        except Exception as e:
            # Catch and log exceptions during user creation.
            # TODO: Make this catch only specific errors and allow others to propagate.
            logger.error(f"Error creating user: {e}")

    access_token = create_jwt(user)

    response = _get_auth_response(access_token, redirect_to_callback)

    set_auth_cookie(request, response, access_token)

    return response


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Login a user using the password auth callback.
    """
    if not config.code.password_auth_callback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No auth_callback defined"
        )

    user = await config.code.password_auth_callback(
        form_data.username, form_data.password
    )

    return await _authenticate_user(request, user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout the user by calling the on_logout callback."""
    clear_auth_cookie(request, response)

    if config.code.on_logout:
        return await config.code.on_logout(request, response)

    return {"success": True}


@router.post("/auth/jwt")
async def jwt_auth(request: Request):
    """Login a user using a valid jwt."""
    from jwt import InvalidTokenError

    auth_header: Optional[str] = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Check if it starts with "Bearer "
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Please use Bearer",
            )
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    try:
        user = decode_jwt(token)
        return await _authenticate_user(request, user)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/auth/header")
async def header_auth(request: Request):
    """Login a user using the header_auth_callback."""
    if not config.code.header_auth_callback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No header_auth_callback defined",
        )

    user = await config.code.header_auth_callback(request.headers)

    return await _authenticate_user(request, user)


@router.get("/auth/oauth/{provider_id}")
async def oauth_login(provider_id: str, request: Request):
    """Redirect the user to the oauth provider login page."""
    if config.code.oauth_callback is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No oauth_callback defined",
        )

    provider = get_oauth_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    random = random_secret(32)

    params = urllib.parse.urlencode(
        {
            "client_id": provider.client_id,
            "redirect_uri": f"{get_user_facing_url(request.url)}/callback",
            "state": random,
            **provider.authorize_params,
        }
    )
    response = RedirectResponse(
        url=f"{provider.authorize_url}?{params}",
    )

    set_oauth_state_cookie(response, random)

    return response


@router.get("/auth/oauth/{provider_id}/callback")
async def oauth_callback(
    provider_id: str,
    request: Request,
    error: Optional[str] = None,
    code: Optional[str] = None,
    state: Optional[str] = None,
):
    """Handle the oauth callback and login the user."""

    if config.code.oauth_callback is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No oauth_callback defined",
        )

    provider = get_oauth_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    if error:
        return _get_oauth_redirect_error(request, error)

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state",
        )

    try:
        validate_oauth_state_cookie(request, state)
    except Exception as e:
        logger.exception("Unable to validate oauth state: %1", e)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    url = get_user_facing_url(request.url)
    token = await provider.get_token(code, url)

    (raw_user_data, default_user) = await provider.get_user_info(token)

    user = await config.code.oauth_callback(
        provider_id, token, raw_user_data, default_user
    )

    response = await _authenticate_user(request, user, redirect_to_callback=True)

    clear_oauth_state_cookie(response)

    return response


# specific route for azure ad hybrid flow
@router.post("/auth/oauth/azure-ad-hybrid/callback")
async def oauth_azure_hf_callback(
    request: Request,
    error: Optional[str] = None,
    code: Annotated[Optional[str], Form()] = None,
    id_token: Annotated[Optional[str], Form()] = None,
):
    """Handle the azure ad hybrid flow callback and login the user."""

    provider_id = "azure-ad-hybrid"
    if config.code.oauth_callback is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No oauth_callback defined",
        )

    provider = get_oauth_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    if error:
        return _get_oauth_redirect_error(request, error)

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code",
        )

    url = get_user_facing_url(request.url)
    token = await provider.get_token(code, url)

    (raw_user_data, default_user) = await provider.get_user_info(token)

    user = await config.code.oauth_callback(
        provider_id, token, raw_user_data, default_user, id_token
    )

    response = await _authenticate_user(request, user, redirect_to_callback=True)

    clear_oauth_state_cookie(response)

    return response


GenericUser = Union[User, PersistedUser, None]
UserParam = Annotated[GenericUser, Depends(get_current_user)]


@router.get("/user")
async def get_user(current_user: UserParam) -> GenericUser:
    return current_user


_language_pattern = (
    "^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,4})?(-[a-zA-Z0-9]{2,8})?(-x-[a-zA-Z0-9]{1,8})?$"
)


@router.post("/set-session-cookie")
async def set_session_cookie(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")

    is_local = request.client and request.client.host in ["127.0.0.1", "localhost"]

    response.set_cookie(
        key="X-Chainlit-Session-id",
        value=session_id,
        path="/",
        httponly=True,
        secure=not is_local,
        samesite="lax" if is_local else "none",
    )

    return {"message": "Session cookie set"}


@router.get("/project/translations")
async def project_translations(
    language: str = Query(
        default="en-US", description="Language code", pattern=_language_pattern
    ),
):
    """Return project translations."""

    # Load translation based on the provided language
    translation = config.load_translation(language)

    return JSONResponse(
        content={
            "translation": translation,
        }
    )


@router.get("/project/settings")
async def project_settings(
    current_user: UserParam,
    language: str = Query(
        default="en-US", description="Language code", pattern=_language_pattern
    ),
):
    """Return project settings. This is called by the UI before the establishing the websocket connection."""

    # Load the markdown file based on the provided language

    markdown = get_markdown_str(config.root, language)

    profiles = []
    if config.code.set_chat_profiles:
        chat_profiles = await config.code.set_chat_profiles(current_user)
        if chat_profiles:
            profiles = [p.to_dict() for p in chat_profiles]

    starters = []
    if config.code.set_starters:
        starters = await config.code.set_starters(current_user)
        if starters:
            starters = [s.to_dict() for s in starters]

    if config.code.on_audio_chunk:
        config.features.audio.enabled = True

    if config.code.on_mcp_connect:
        config.features.mcp.enabled = True

    debug_url = None
    data_layer = get_data_layer()

    if data_layer and config.run.debug:
        debug_url = await data_layer.build_debug_url()

    return JSONResponse(
        content={
            "ui": config.ui.to_dict(),
            "features": config.features.to_dict(),
            "userEnv": config.project.user_env,
            "dataPersistence": get_data_layer() is not None,
            "threadResumable": bool(config.code.on_chat_resume),
            "markdown": markdown,
            "chatProfiles": profiles,
            "starters": starters,
            "debugUrl": debug_url,
        }
    )


@router.put("/feedback")
async def update_feedback(
    request: Request,
    update: UpdateFeedbackRequest,
    current_user: UserParam,
):
    """Update the human feedback for a particular message."""
    data_layer = get_data_layer()
    if not data_layer:
        raise HTTPException(status_code=500, detail="Data persistence is not enabled")

    try:
        feedback_id = await data_layer.upsert_feedback(feedback=update.feedback)

        if config.code.on_feedback:
            try:
                await config.code.on_feedback(update.feedback)
            except Exception as callback_error:
                logger.error(
                    f"Error in user-provided on_feedback callback: {callback_error}"
                )
                # Optionally, you could continue without raising an exception to avoid disrupting the endpoint.
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500) from e

    return JSONResponse(content={"success": True, "feedbackId": feedback_id})


@router.delete("/feedback")
async def delete_feedback(
    request: Request,
    payload: DeleteFeedbackRequest,
    current_user: UserParam,
):
    """Delete a feedback."""

    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    feedback_id = payload.feedbackId

    await data_layer.delete_feedback(feedback_id)
    return JSONResponse(content={"success": True})


@router.post("/project/threads")
async def get_user_threads(
    request: Request,
    payload: GetThreadsRequest,
    current_user: UserParam,
):
    """Get the threads page by page."""

    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not isinstance(current_user, PersistedUser):
        persisted_user = await data_layer.get_user(identifier=current_user.identifier)
        if not persisted_user:
            raise HTTPException(status_code=404, detail="User not found")
        payload.filter.userId = persisted_user.id
    else:
        payload.filter.userId = current_user.id

    res = await data_layer.list_threads(payload.pagination, payload.filter)
    return JSONResponse(content=res.to_dict())


@router.get("/project/thread/{thread_id}")
async def get_thread(
    request: Request,
    thread_id: str,
    current_user: UserParam,
):
    """Get a specific thread."""
    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    await is_thread_author(current_user.identifier, thread_id)

    res = await data_layer.get_thread(thread_id)
    return JSONResponse(content=res)


@router.get("/project/thread/{thread_id}/element/{element_id}")
async def get_thread_element(
    request: Request,
    thread_id: str,
    element_id: str,
    current_user: UserParam,
):
    """Get a specific thread element."""
    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    await is_thread_author(current_user.identifier, thread_id)

    res = await data_layer.get_element(thread_id, element_id)
    return JSONResponse(content=res)


@router.put("/project/element")
async def update_thread_element(
    payload: ElementRequest,
    current_user: UserParam,
):
    """Update a specific thread element."""

    from chainlit.context import init_ws_context
    from chainlit.element import Element, ElementDict
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(payload.sessionId)
    context = init_ws_context(session)

    element_dict = cast(ElementDict, payload.element)

    if element_dict["type"] != "custom":
        return {"success": False}

    element = Element.from_dict(element_dict)

    if current_user:
        if (
            not context.session.user
            or context.session.user.identifier != current_user.identifier
        ):
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to update elements for this session",
            )

    await element.update()
    return {"success": True}


@router.delete("/project/element")
async def delete_thread_element(
    payload: ElementRequest,
    current_user: UserParam,
):
    """Delete a specific thread element."""

    from chainlit.context import init_ws_context
    from chainlit.element import CustomElement, ElementDict
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(payload.sessionId)
    context = init_ws_context(session)

    element_dict = cast(ElementDict, payload.element)

    if element_dict["type"] != "custom":
        return {"success": False}

    element = CustomElement(
        id=element_dict["id"],
        object_key=element_dict["objectKey"],
        chainlit_key=element_dict["chainlitKey"],
        url=element_dict["url"],
        for_id=element_dict.get("forId") or "",
        thread_id=element_dict.get("threadId") or "",
        name=element_dict["name"],
        props=element_dict.get("props") or {},
        display=element_dict["display"],
    )

    if current_user:
        if (
            not context.session.user
            or context.session.user.identifier != current_user.identifier
        ):
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to remove elements for this session",
            )

    await element.remove()

    return {"success": True}


@router.put("/project/thread")
async def rename_thread(
    request: Request,
    payload: UpdateThreadRequest,
    current_user: UserParam,
):
    """Rename a thread."""

    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    thread_id = payload.threadId

    await is_thread_author(current_user.identifier, thread_id)

    await data_layer.update_thread(thread_id, name=payload.name)
    return JSONResponse(content={"success": True})


@router.delete("/project/thread")
async def delete_thread(
    request: Request,
    payload: DeleteThreadRequest,
    current_user: UserParam,
):
    """Delete a thread."""

    data_layer = get_data_layer()

    if not data_layer:
        raise HTTPException(status_code=400, detail="Data persistence is not enabled")

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    thread_id = payload.threadId

    await is_thread_author(current_user.identifier, thread_id)

    await data_layer.delete_thread(thread_id)
    return JSONResponse(content={"success": True})


@router.post("/project/action")
async def call_action(
    payload: CallActionRequest,
    current_user: UserParam,
):
    """Run an action."""

    from chainlit.action import Action
    from chainlit.context import init_ws_context
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(payload.sessionId)
    context = init_ws_context(session)

    action = Action(**payload.action)

    if current_user:
        if (
            not context.session.user
            or context.session.user.identifier != current_user.identifier
        ):
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to upload files for this session",
            )

    callback = config.code.action_callbacks.get(action.name)
    if callback:
        if not context.session.has_first_interaction:
            context.session.has_first_interaction = True
            asyncio.create_task(context.emitter.init_thread(action.name))

        response = await callback(action)
    else:
        raise HTTPException(
            status_code=404,
            detail=f"No callback found for action {action.name}",
        )

    return JSONResponse(content={"success": True, "response": response})


@router.post("/mcp")
async def connect_mcp(
    payload: ConnectMCPRequest,
    current_user: UserParam,
):
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.stdio import (
        StdioServerParameters,
        get_default_environment,
        stdio_client,
    )

    from chainlit.context import init_ws_context
    from chainlit.mcp import SseMcpConnection, StdioMcpConnection, validate_mcp_command
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(payload.sessionId)
    context = init_ws_context(session)

    if current_user:
        if (
            not context.session.user
            or context.session.user.identifier != current_user.identifier
        ):
            raise HTTPException(
                status_code=401,
            )

    mcp_enabled = config.code.on_mcp_connect is not None
    if mcp_enabled:
        if payload.name in session.mcp_sessions:
            old_client_session, old_exit_stack = session.mcp_sessions[payload.name]
            if on_mcp_disconnect := config.code.on_mcp_disconnect:
                await on_mcp_disconnect(payload.name, old_client_session)
            try:
                await old_exit_stack.aclose()
            except Exception:
                pass

        try:
            exit_stack = AsyncExitStack()

            if payload.clientType == "sse":
                if not config.features.mcp.sse.enabled:
                    raise HTTPException(
                        status_code=400,
                        detail="SSE MCP is not enabled",
                    )

                mcp_connection = SseMcpConnection(url=payload.url, name=payload.name)  # type: SseMcpConnection

                transport = await exit_stack.enter_async_context(
                    sse_client(url=mcp_connection.url)
                )
            elif payload.clientType == "stdio":
                if not config.features.mcp.stdio.enabled:
                    raise HTTPException(
                        status_code=400,
                        detail="Stdio MCP is not enabled",
                    )

                env_from_cmd, command, args = validate_mcp_command(payload.fullCommand)
                mcp_connection = StdioMcpConnection(  # type: ignore[no-redef]
                    command=command, args=args, name=payload.name
                )  # type: StdioMcpConnection

                env = get_default_environment()
                env.update(env_from_cmd)
                # Create the server parameters
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env,
                )

                transport = await exit_stack.enter_async_context(
                    stdio_client(server_params)
                )

            read, write = transport

            mcp_session: ClientSession = await exit_stack.enter_async_context(
                ClientSession(
                    read_stream=read, write_stream=write, sampling_callback=None
                )
            )

            # Initialize the session
            await mcp_session.initialize()

            # Store the session
            session.mcp_sessions[mcp_connection.name] = (mcp_session, exit_stack)

            # Call the callback
            await config.code.on_mcp_connect(mcp_connection, mcp_session)

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not connect to the MCP: {e!s}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="This app does not support MCP.",
        )

    tool_list = await mcp_session.list_tools()

    return JSONResponse(
        content={
            "success": True,
            "mcp": {
                "name": payload.name,
                "tools": [{"name": t.name} for t in tool_list.tools],
                "clientType": payload.clientType,
                "command": payload.fullCommand
                if payload.clientType == "stdio"
                else None,
                "url": payload.url if payload.clientType == "sse" else None,
            },
        }
    )


@router.delete("/mcp")
async def disconnect_mcp(
    payload: DisconnectMCPRequest,
    current_user: UserParam,
):
    from chainlit.context import init_ws_context
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(payload.sessionId)
    context = init_ws_context(session)

    if current_user:
        if (
            not context.session.user
            or context.session.user.identifier != current_user.identifier
        ):
            raise HTTPException(
                status_code=401,
            )

    callback = config.code.on_mcp_disconnect
    if payload.name in session.mcp_sessions:
        try:
            client_session, exit_stack = session.mcp_sessions[payload.name]
            if callback:
                await callback(payload.name, client_session)

            try:
                await exit_stack.aclose()
            except Exception:
                pass
            del session.mcp_sessions[payload.name]

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not disconnect to the MCP: {e!s}",
            )

    return JSONResponse(content={"success": True})


@router.post("/project/file")
async def upload_file(
    current_user: UserParam,
    session_id: str,
    file: UploadFile,
):
    """Upload a file to the session files directory."""

    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    if current_user:
        if not session.user or session.user.identifier != current_user.identifier:
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to upload files for this session",
            )

    session.files_dir.mkdir(exist_ok=True)

    try:
        content = await file.read()

        assert file.filename, "No filename for uploaded file"
        assert file.content_type, "No content type for uploaded file"

        try:
            validate_file_upload(file)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        file_response = await session.persist_file(
            name=file.filename, content=content, mime=file.content_type
        )

        return JSONResponse(content=file_response)
    finally:
        await file.close()


def validate_file_upload(file: UploadFile):
    """Validate the file upload as configured in config.features.spontaneous_file_upload.
    Args:
        file (UploadFile): The file to validate.
    Raises:
        ValueError: If the file is not allowed.
    """
    # TODO: This logic/endpoint is shared across spontaneous uploads and the AskFileMessage API.
    # Commenting this check until we find a better solution

    # if config.features.spontaneous_file_upload is None:
    #     """Default for a missing config is to allow the fileupload without any restrictions"""
    #     return
    # if not config.features.spontaneous_file_upload.enabled:
    #     raise ValueError("File upload is not enabled")

    validate_file_mime_type(file)
    validate_file_size(file)


def validate_file_mime_type(file: UploadFile):
    """Validate the file mime type as configured in config.features.spontaneous_file_upload.
    Args:
        file (UploadFile): The file to validate.
    Raises:
        ValueError: If the file type is not allowed.
    """

    if (
        config.features.spontaneous_file_upload is None
        or config.features.spontaneous_file_upload.accept is None
    ):
        "Accept is not configured, allowing all file types"
        return

    accept = config.features.spontaneous_file_upload.accept

    assert isinstance(accept, List) or isinstance(accept, dict), (
        "Invalid configuration for spontaneous_file_upload, accept must be a list or a dict"
    )

    if isinstance(accept, List):
        for pattern in accept:
            if fnmatch.fnmatch(file.content_type, pattern):
                return
    elif isinstance(accept, dict):
        for pattern, extensions in accept.items():
            if fnmatch.fnmatch(file.content_type, pattern):
                if len(extensions) == 0:
                    return
                for extension in extensions:
                    if file.filename is not None and file.filename.lower().endswith(
                        extension.lower()
                    ):
                        return
    raise ValueError("File type not allowed")


def validate_file_size(file: UploadFile):
    """Validate the file size as configured in config.features.spontaneous_file_upload.
    Args:
        file (UploadFile): The file to validate.
    Raises:
        ValueError: If the file size is too large.
    """
    if (
        config.features.spontaneous_file_upload is None
        or config.features.spontaneous_file_upload.max_size_mb is None
    ):
        return

    if (
        file.size is not None
        and file.size
        > config.features.spontaneous_file_upload.max_size_mb * 1024 * 1024
    ):
        raise ValueError("File size too large")


@router.get("/project/file/{file_id}")
async def get_file(
    file_id: str,
    session_id: str,
    current_user: UserParam,
):
    """Get a file from the session files directory."""
    from chainlit.session import WebsocketSession

    session = WebsocketSession.get_by_id(session_id) if session_id else None

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    if current_user:
        if not session.user or session.user.identifier != current_user.identifier:
            raise HTTPException(
                status_code=401,
                detail="You are not authorized to download files from this session",
            )

    if file_id in session.files:
        file = session.files[file_id]
        return FileResponse(file["path"], media_type=file["type"])
    else:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/favicon")
async def get_favicon():
    """Get the favicon for the UI."""
    custom_favicon_path = os.path.join(APP_ROOT, "public", "favicon.*")
    files = glob.glob(custom_favicon_path)

    if files:
        favicon_path = files[0]
    else:
        favicon_path = os.path.join(build_dir, "favicon.svg")

    media_type, _ = mimetypes.guess_type(favicon_path)

    return FileResponse(favicon_path, media_type=media_type)


@router.get("/logo")
async def get_logo(theme: Optional[Theme] = Query(Theme.light)):
    """Get the default logo for the UI."""
    theme_value = theme.value if theme else Theme.light.value
    logo_path = None

    for path in [
        os.path.join(APP_ROOT, "public", f"logo_{theme_value}.*"),
        os.path.join(build_dir, "assets", f"logo_{theme_value}*.*"),
    ]:
        files = glob.glob(path)

        if files:
            logo_path = files[0]
            break

    if not logo_path:
        raise HTTPException(status_code=404, detail="Missing default logo")

    media_type, _ = mimetypes.guess_type(logo_path)

    return FileResponse(logo_path, media_type=media_type)


@router.get("/avatars/{avatar_id:str}")
async def get_avatar(avatar_id: str):
    """Get the avatar for the user based on the avatar_id."""
    if not re.match(r"^[a-zA-Z0-9_ .-]+$", avatar_id):
        raise HTTPException(status_code=400, detail="Invalid avatar_id")

    if avatar_id == "default":
        avatar_id = config.ui.name

    avatar_id = avatar_id.strip().lower().replace(" ", "_").replace(".", "_")

    base_path = Path(APP_ROOT) / "public" / "avatars"
    avatar_pattern = f"{avatar_id}.*"

    matching_files = base_path.glob(avatar_pattern)

    if avatar_path := next(matching_files, None):
        if not is_path_inside(avatar_path, base_path):
            raise HTTPException(status_code=400, detail="Invalid filename")
        media_type, _ = mimetypes.guess_type(str(avatar_path))

        return FileResponse(avatar_path, media_type=media_type)

    return await get_favicon()


@router.head("/")
def status_check():
    """Check if the site is operational."""
    return {"message": "Site is operational"}


@router.get("/{full_path:path}")
async def serve(request: Request):
    """Serve the UI files."""
    root_path = os.getenv("CHAINLIT_PARENT_ROOT_PATH", "") + os.getenv(
        "CHAINLIT_ROOT_PATH", ""
    )
    html_template = get_html_template(root_path)
    response = HTMLResponse(content=html_template, status_code=200)

    return response


app.include_router(router)

import chainlit.socket  # noqa
