import asyncio
import os

import click
import nest_asyncio
import uvicorn

# Not sure if it is necessary to call nest_asyncio.apply() before the other imports
nest_asyncio.apply()

# ruff: noqa: E402
from chainlit.auth import ensure_jwt_secret
from chainlit.cache import init_lc_cache
from chainlit.config import (
    BACKEND_ROOT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_ROOT_PATH,
    config,
    init_config,
    lint_translations,
    load_module,
)
from chainlit.logger import logger
from chainlit.markdown import init_markdown
from chainlit.secret import random_secret
from chainlit.utils import check_file


def assert_app():
    if (
        not config.code.on_chat_start
        and not config.code.on_message
        and not config.code.on_audio_chunk
    ):
        raise Exception(
            "You need to configure at least one of on_chat_start, on_message or on_audio_chunk callback"
        )


# Create the main command group for Chainlit CLI
@click.group(context_settings={"auto_envvar_prefix": "CHAINLIT"})
@click.version_option(prog_name="Chainlit")
def cli():
    return


# Define the function to run Chainlit with provided options
def run_chainlit(target: str):
    host = os.environ.get("CHAINLIT_HOST", DEFAULT_HOST)
    port = int(os.environ.get("CHAINLIT_PORT", DEFAULT_PORT))
    root_path = os.environ.get("CHAINLIT_ROOT_PATH", DEFAULT_ROOT_PATH)

    ssl_certfile = os.environ.get("CHAINLIT_SSL_CERT", None)
    ssl_keyfile = os.environ.get("CHAINLIT_SSL_KEY", None)

    ws_per_message_deflate_env = os.environ.get(
        "UVICORN_WS_PER_MESSAGE_DEFLATE", "true"
    )
    ws_per_message_deflate = ws_per_message_deflate_env.lower() in [
        "true",
        "1",
        "yes",
    ]  # Convert to boolean

    ws_protocol = os.environ.get("UVICORN_WS_PROTOCOL", "auto")

    config.run.host = host
    config.run.port = port
    config.run.root_path = root_path

    from chainlit.server import app

    check_file(target)
    # Load the module provided by the user
    config.run.module_name = target
    load_module(config.run.module_name)

    ensure_jwt_secret()
    assert_app()

    # Create the chainlit.md file if it doesn't exist
    init_markdown(config.root)

    # Initialize the LangChain cache if installed and enabled
    init_lc_cache()

    log_level = "debug" if config.run.debug else "error"

    # Start the server
    async def start():
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            ws=ws_protocol,
            log_level=log_level,
            ws_per_message_deflate=ws_per_message_deflate,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
        )
        server = uvicorn.Server(config)
        await server.serve()

    # Run the asyncio event loop instead of uvloop to enable re entrance
    asyncio.run(start())
    # uvicorn.run(app, host=host, port=port, log_level=log_level)


# Define the "run" command for Chainlit CLI
@cli.command("run")
@click.argument("target", required=True, envvar="RUN_TARGET")
@click.option(
    "-w",
    "--watch",
    default=False,
    is_flag=True,
    envvar="WATCH",
    help="Reload the app when the module changes",
)
@click.option(
    "-h",
    "--headless",
    default=False,
    is_flag=True,
    envvar="HEADLESS",
    help="Will prevent to auto open the app in the browser",
)
@click.option(
    "-d",
    "--debug",
    default=False,
    is_flag=True,
    envvar="DEBUG",
    help="Set the log level to debug",
)
@click.option(
    "-c",
    "--ci",
    default=False,
    is_flag=True,
    envvar="CI",
    help="Flag to run in CI mode",
)
@click.option(
    "--no-cache",
    default=False,
    is_flag=True,
    envvar="NO_CACHE",
    help="Useful to disable third parties cache, such as langchain.",
)
@click.option(
    "--ssl-cert",
    default=None,
    envvar="CHAINLIT_SSL_CERT",
    help="Specify the file path for the SSL certificate.",
)
@click.option(
    "--ssl-key",
    default=None,
    envvar="CHAINLIT_SSL_KEY",
    help="Specify the file path for the SSL key",
)
@click.option("--host", help="Specify a different host to run the server on")
@click.option("--port", help="Specify a different port to run the server on")
@click.option("--root-path", help="Specify a different root path to run the server on")
def chainlit_run(
    target,
    watch,
    headless,
    debug,
    ci,
    no_cache,
    ssl_cert,
    ssl_key,
    host,
    port,
    root_path,
):
    if host:
        os.environ["CHAINLIT_HOST"] = host
    if port:
        os.environ["CHAINLIT_PORT"] = port
    if bool(ssl_cert) != bool(ssl_key):
        raise click.UsageError(
            "Both --ssl-cert and --ssl-key must be provided together."
        )
    if ssl_cert:
        os.environ["CHAINLIT_SSL_CERT"] = ssl_cert
        os.environ["CHAINLIT_SSL_KEY"] = ssl_key
    if root_path:
        os.environ["CHAINLIT_ROOT_PATH"] = root_path
    if ci:
        logger.info("Running in CI mode")

        no_cache = True
        # This is required to have OpenAI LLM providers available for the CI run
        os.environ["OPENAI_API_KEY"] = "sk-FAKE-OPENAI-API-KEY"
        # This is required for authentication tests
        os.environ["CHAINLIT_AUTH_SECRET"] = "SUPER_SECRET"  # nosec B105

    config.run.headless = headless
    config.run.debug = debug
    config.run.no_cache = no_cache
    config.run.ci = ci
    config.run.watch = watch
    config.run.ssl_cert = ssl_cert
    config.run.ssl_key = ssl_key

    run_chainlit(target)


@cli.command("hello")
@click.argument("args", nargs=-1)
def chainlit_hello(args=None, **kwargs):
    hello_path = os.path.join(BACKEND_ROOT, "hello.py")
    run_chainlit(hello_path)


@cli.command("init")
@click.argument("args", nargs=-1)
def chainlit_init(args=None, **kwargs):
    init_config(log=True)


@cli.command("create-secret")
@click.argument("args", nargs=-1)
def chainlit_create_secret(args=None, **kwargs):
    print(
        f'Copy the following secret into your .env file. Once it is set, changing it will logout all users with active sessions.\nCHAINLIT_AUTH_SECRET="{random_secret()}"'
    )


@cli.command("lint-translations")
@click.argument("args", nargs=-1)
def chainlit_lint_translations(args=None, **kwargs):
    lint_translations()
