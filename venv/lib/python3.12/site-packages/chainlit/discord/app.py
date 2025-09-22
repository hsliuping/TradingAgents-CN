import asyncio
import mimetypes
import re
import uuid
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Dict, List, Optional, Union

if TYPE_CHECKING:
    from discord.abc import MessageableChannel

import discord
import filetype
import httpx
from discord.ui import Button, View

from chainlit.config import config
from chainlit.context import ChainlitContext, HTTPSession, context, context_var
from chainlit.data import get_data_layer
from chainlit.element import Element, ElementDict
from chainlit.emitter import BaseChainlitEmitter
from chainlit.logger import logger
from chainlit.message import Message, StepDict
from chainlit.types import Feedback
from chainlit.user import PersistedUser, User
from chainlit.user_session import user_session


class FeedbackView(View):
    def __init__(self, step_id: str):
        super().__init__(timeout=None)
        self.step_id = step_id

    @discord.ui.button(label="👎")
    async def thumbs_down(self, interaction: discord.Interaction, button: Button):
        if data_layer := get_data_layer():
            try:
                feedback = Feedback(forId=self.step_id, value=0)
                await data_layer.upsert_feedback(feedback)
            except Exception as e:
                logger.error(f"Error upserting feedback: {e}")
        if interaction.message:
            await interaction.message.edit(view=None)
            await interaction.message.add_reaction("👎")

    @discord.ui.button(label="👍")
    async def thumbs_up(self, interaction: discord.Interaction, button: Button):
        if data_layer := get_data_layer():
            try:
                feedback = Feedback(forId=self.step_id, value=1)
                await data_layer.upsert_feedback(feedback)
            except Exception as e:
                logger.error(f"Error upserting feedback: {e}")
        if interaction.message:
            await interaction.message.edit(view=None)
            await interaction.message.add_reaction("👍")


class DiscordEmitter(BaseChainlitEmitter):
    def __init__(self, session: HTTPSession, channel: "MessageableChannel"):
        super().__init__(session)
        self.channel = channel

    async def send_element(self, element_dict: ElementDict):
        if element_dict.get("display") != "inline":
            return

        persisted_file = self.session.files.get(element_dict.get("chainlitKey") or "")
        file: Optional[Union[BytesIO, str]] = None
        mime: Optional[str] = None

        if persisted_file:
            file = str(persisted_file["path"])
            mime = element_dict.get("mime")
        elif file_url := element_dict.get("url"):
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url)
                if response.status_code == 200:
                    file = BytesIO(response.content)
                    mime = filetype.guess_mime(file)

        if not file:
            return

        element_name: str = element_dict.get("name", "Untitled")

        if mime:
            file_extension = mimetypes.guess_extension(mime)
            if file_extension:
                element_name += file_extension

        file_obj = discord.File(file, filename=element_name)
        await self.channel.send(file=file_obj)

    async def send_step(self, step_dict: StepDict):
        if not step_dict["type"] == "assistant_message":
            return

        step_type = step_dict.get("type")
        is_message = step_type in [
            "user_message",
            "assistant_message",
        ]
        is_empty_output = not step_dict.get("output")

        if is_empty_output or not is_message:
            return
        else:
            enable_feedback = get_data_layer()
            message = await self.channel.send(step_dict["output"])

            if enable_feedback:
                current_run = context.current_run
                scorable_id = current_run.id if current_run else step_dict.get("id")
                if not scorable_id:
                    return
                view = FeedbackView(scorable_id)
                await message.edit(view=view)

    async def update_step(self, step_dict: StepDict):
        if not step_dict["type"] == "assistant_message":
            return

        await self.send_step(step_dict)


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


def init_discord_context(
    session: HTTPSession,
    channel: "MessageableChannel",
    message: discord.Message,
) -> ChainlitContext:
    emitter = DiscordEmitter(session=session, channel=channel)
    context = ChainlitContext(session=session, emitter=emitter)
    context_var.set(context)
    user_session.set("discord_message", message)
    user_session.set("discord_channel", channel)
    return context


users_by_discord_id: Dict[int, Union[User, PersistedUser]] = {}

USER_PREFIX = "discord_"


async def get_user(discord_user: Union[discord.User, discord.Member]):
    if discord_user.id in users_by_discord_id:
        return users_by_discord_id[discord_user.id]

    metadata = {
        "name": discord_user.name,
        "id": discord_user.id,
    }
    user = User(identifier=USER_PREFIX + str(discord_user.name), metadata=metadata)

    users_by_discord_id[discord_user.id] = user

    if data_layer := get_data_layer():
        try:
            persisted_user = await data_layer.create_user(user)
            if persisted_user:
                users_by_discord_id[discord_user.id] = persisted_user
        except Exception as e:
            logger.error(f"Error creating user: {e}")

    return users_by_discord_id[discord_user.id]


async def download_discord_file(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.content
        else:
            return None


async def download_discord_files(
    session: HTTPSession, attachments: List[discord.Attachment]
):
    download_coros = [
        download_discord_file(attachment.url) for attachment in attachments
    ]
    file_bytes_list = await asyncio.gather(*download_coros)
    file_refs = []
    for idx, file_bytes in enumerate(file_bytes_list):
        if file_bytes:
            name = attachments[idx].filename
            mime_type = attachments[idx].content_type or "application/octet-stream"
            file_ref = await session.persist_file(
                name=name, mime=mime_type, content=file_bytes
            )
            file_refs.append(file_ref)

    files_dicts = [
        session.files[file["id"]] for file in file_refs if file["id"] in session.files
    ]

    elements = [
        Element.from_dict(
            {
                "id": file["id"],
                "name": file["name"],
                "path": str(file["path"]),
                "chainlitKey": file["id"],
                "display": "inline",
                "type": Element.infer_type_from_mime(file["type"]),
            }
        )
        for file in files_dicts
    ]

    return elements


def clean_content(message: discord.Message):
    if not client.user:
        return message.content

    # Regex to find mentions of the bot
    bot_mention = f"<@!?{client.user.id}>"
    # Replace the bot's mention with nothing
    return re.sub(bot_mention, "", message.content).strip()


async def process_discord_message(
    message: discord.Message,
    thread_id: str,
    thread_name: str,
    channel: "MessageableChannel",
    bind_thread_to_user=False,
):
    user = await get_user(message.author)

    text = clean_content(message)
    discord_files = message.attachments

    session_id = str(uuid.uuid4())
    session = HTTPSession(
        id=session_id,
        thread_id=thread_id,
        user=user,
        client_type="discord",
    )

    ctx = init_discord_context(
        session=session,
        channel=channel,
        message=message,
    )

    file_elements = await download_discord_files(session, discord_files)

    if on_chat_start := config.code.on_chat_start:
        await on_chat_start()

    msg = Message(
        content=text,
        elements=file_elements,
        type="user_message",
        author=user.metadata.get("name"),
    )

    await msg.send()

    if on_message := config.code.on_message:
        async with channel.typing():
            await on_message(msg)

    if on_chat_end := config.code.on_chat_end:
        await on_chat_end()

    if data_layer := get_data_layer():
        user_id = None
        if isinstance(user, PersistedUser):
            user_id = user.id if bind_thread_to_user else None

        try:
            await data_layer.update_thread(
                thread_id=thread_id,
                name=thread_name,
                metadata=ctx.session.to_persistable(),
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"Error updating thread: {e}")

    await ctx.session.delete()


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    if not client.user or message.author == client.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    if not client.user.mentioned_in(message) and not is_dm:
        return

    thread_name: str = ""
    thread_id: str = ""
    bind_thread_to_user = False
    channel = message.channel

    if isinstance(message.channel, discord.Thread):
        thread_name = f"{message.channel.name}"
        thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(channel.id)))
    elif isinstance(message.channel, discord.ForumChannel):
        thread_name = f"{message.channel.name}"
        thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(channel.id)))
    elif isinstance(message.channel, discord.DMChannel):
        thread_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                str(channel.id) + datetime.today().strftime("%Y-%m-%d"),
            )
        )
        thread_name = (
            f"{message.author} Discord DM {datetime.today().strftime('%Y-%m-%d')}"
        )
        bind_thread_to_user = True
    elif isinstance(message.channel, discord.GroupChannel):
        thread_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                str(channel.id) + datetime.today().strftime("%Y-%m-%d"),
            )
        )
        thread_name = f"{message.channel.name}"
    elif isinstance(message.channel, discord.TextChannel):
        # Discord limits thread names to 100 characters and does not create
        # threads from empty messages.
        thread_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                str(channel.id) + datetime.today().strftime("%Y-%m-%d"),
            )
        )
        discord_thread_name = clean_content(message)[:100] or "Untitled"
        channel = await message.channel.create_thread(
            name=discord_thread_name, message=message
        )
        thread_name = f"{channel.name}"
    else:
        logger.warning(f"Unsupported channel type: {message.channel.type}")
        return

    await process_discord_message(
        message=message,
        thread_id=thread_id,
        thread_name=thread_name,
        channel=channel,
        bind_thread_to_user=bind_thread_to_user,
    )
