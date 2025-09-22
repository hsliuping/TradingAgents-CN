import asyncio
import base64
import mimetypes
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union

import filetype

if TYPE_CHECKING:
    from botbuilder.core import TurnContext
    from botbuilder.schema import Activity

import httpx
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    MessageFactory,
    TurnContext,
)
from botbuilder.schema import (
    ActionTypes,
    Activity,
    ActivityTypes,
    Attachment,
    CardAction,
    ChannelAccount,
    HeroCard,
)

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


class TeamsEmitter(BaseChainlitEmitter):
    def __init__(self, session: HTTPSession, turn_context: TurnContext):
        super().__init__(session)
        self.turn_context = turn_context

    async def send_element(self, element_dict: ElementDict):
        if element_dict.get("display") != "inline":
            return

        persisted_file = self.session.files.get(element_dict.get("chainlitKey") or "")
        attachment: Optional[Attachment] = None
        mime: Optional[str] = None

        element_name: str = element_dict.get("name", "Untitled")

        if mime:
            file_extension = mimetypes.guess_extension(mime)
            if file_extension:
                element_name += file_extension

        if persisted_file:
            mime = element_dict.get("mime")
            with open(persisted_file["path"], "rb") as file:
                dencoded_string = base64.b64encode(file.read()).decode()
                content_url = f"data:{mime};base64,{dencoded_string}"
                attachment = Attachment(
                    content_type=mime, content_url=content_url, name=element_name
                )

        elif url := element_dict.get("url"):
            attachment = Attachment(
                content_type=mime, content_url=url, name=element_name
            )

        if not attachment:
            return

        await self.turn_context.send_activity(Activity(attachments=[attachment]))

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
            reply = MessageFactory.text(step_dict["output"])
            enable_feedback = get_data_layer()
            if enable_feedback:
                current_run = context.current_run
                scorable_id = current_run.id if current_run else step_dict["id"]
                like_button = CardAction(
                    type=ActionTypes.message_back,
                    title="👍",
                    text="like",
                    value={"feedback": "like", "step_id": scorable_id},
                )
                dislike_button = CardAction(
                    type=ActionTypes.message_back,
                    title="👎",
                    text="dislike",
                    value={"feedback": "dislike", "step_id": scorable_id},
                )
                card = HeroCard(buttons=[like_button, dislike_button])
                attachment = Attachment(
                    content_type="application/vnd.microsoft.card.hero", content=card
                )
                reply.attachments = [attachment]

            await self.turn_context.send_activity(reply)

    async def update_step(self, step_dict: StepDict):
        if not step_dict["type"] == "assistant_message":
            return

        await self.send_step(step_dict)


adapter_settings = BotFrameworkAdapterSettings(
    app_id=os.environ.get("TEAMS_APP_ID"),
    app_password=os.environ.get("TEAMS_APP_PASSWORD"),
)
adapter = BotFrameworkAdapter(adapter_settings)


def init_teams_context(
    session: HTTPSession,
    turn_context: TurnContext,
) -> ChainlitContext:
    emitter = TeamsEmitter(session=session, turn_context=turn_context)
    context = ChainlitContext(session=session, emitter=emitter)
    context_var.set(context)
    user_session.set("teams_turn_context", turn_context)
    return context


users_by_teams_id: Dict[str, Union[User, PersistedUser]] = {}

USER_PREFIX = "teams_"


async def get_user(teams_user: ChannelAccount):
    if teams_user.id in users_by_teams_id:
        return users_by_teams_id[teams_user.id]

    metadata = {
        "name": teams_user.name,
        "id": teams_user.id,
    }
    user = User(identifier=USER_PREFIX + str(teams_user.name), metadata=metadata)

    users_by_teams_id[teams_user.id] = user

    if data_layer := get_data_layer():
        try:
            persisted_user = await data_layer.create_user(user)
            if persisted_user:
                users_by_teams_id[teams_user.id] = persisted_user
        except Exception as e:
            logger.error(f"Error creating user: {e}")

    return users_by_teams_id[teams_user.id]


async def download_teams_file(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.content
        else:
            return None


async def download_teams_files(
    session: HTTPSession, attachments: Optional[List[Attachment]] = None
):
    if not attachments:
        return []

    attachments = [
        attachment for attachment in attachments if isinstance(attachment.content, dict)
    ]
    download_coros = [
        download_teams_file(attachment.content.get("downloadUrl"))
        for attachment in attachments
    ]
    file_bytes_list = await asyncio.gather(*download_coros)
    file_refs = []
    for idx, file_bytes in enumerate(file_bytes_list):
        if file_bytes:
            name = attachments[idx].name
            mime_type = filetype.guess_mime(file_bytes) or "application/octet-stream"
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


def clean_content(activity: Activity):
    return activity.text.strip()


async def process_teams_message(
    turn_context: TurnContext,
    thread_name: str,
):
    user = await get_user(turn_context.activity.from_property)

    thread_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_DNS,
            str(
                turn_context.activity.conversation.id
                + datetime.today().strftime("%Y-%m-%d")
            ),
        )
    )

    text = clean_content(turn_context.activity)
    teams_files = turn_context.activity.attachments

    session_id = str(uuid.uuid4())

    session = HTTPSession(
        id=session_id,
        thread_id=thread_id,
        user=user,
        client_type="teams",
    )

    ctx = init_teams_context(
        session=session,
        turn_context=turn_context,
    )

    file_elements = await download_teams_files(session, teams_files)

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
        await on_message(msg)

    if on_chat_end := config.code.on_chat_end:
        await on_chat_end()

    if data_layer := get_data_layer():
        if isinstance(user, PersistedUser):
            try:
                await data_layer.update_thread(
                    thread_id=thread_id,
                    name=thread_name,
                    metadata=ctx.session.to_persistable(),
                    user_id=user.id,
                )
            except Exception as e:
                logger.error(f"Error updating thread: {e}")

    await ctx.session.delete()


async def handle_message(turn_context: TurnContext):
    if turn_context.activity.type == ActivityTypes.message:
        if (
            turn_context.activity.text == "like"
            or turn_context.activity.text == "dislike"
        ):
            feedback_value: Literal[0, 1] = (
                0 if turn_context.activity.text == "dislike" else 1
            )
            step_id = turn_context.activity.value.get("step_id")
            if data_layer := get_data_layer():
                await data_layer.upsert_feedback(
                    Feedback(forId=step_id, value=feedback_value)
                )
            updated_text = "👍" if turn_context.activity.text == "like" else "👎"
            # Update the existing message to remove the buttons
            updated_message = Activity(
                type=ActivityTypes.message,
                id=turn_context.activity.reply_to_id,
                text=updated_text,
                attachments=[],
            )
            await turn_context.update_activity(updated_message)
        else:
            # Send typing activity
            typing_activity = Activity(
                type=ActivityTypes.typing,
                from_property=turn_context.activity.recipient,
                recipient=turn_context.activity.from_property,
                conversation=turn_context.activity.conversation,
            )
            await turn_context.send_activity(typing_activity)
            thread_name = f"{turn_context.activity.from_property.name} Teams DM {datetime.today().strftime('%Y-%m-%d')}"
            await process_teams_message(turn_context, thread_name)


async def on_turn(turn_context: TurnContext):
    await handle_message(turn_context)


# Create the main bot class
class TeamsBot:
    async def on_turn(self, turn_context: TurnContext):
        await on_turn(turn_context)


# Create the bot instance
bot = TeamsBot()
