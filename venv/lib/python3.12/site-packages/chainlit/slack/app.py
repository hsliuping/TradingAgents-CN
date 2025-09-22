import asyncio
import os
import re
import uuid
from functools import partial
from typing import Dict, List, Optional, Union

import httpx
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

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


class SlackEmitter(BaseChainlitEmitter):
    def __init__(
        self,
        session: HTTPSession,
        app: AsyncApp,
        channel_id: str,
        say,
        thread_ts: Optional[str] = None,
    ):
        super().__init__(session)
        self.app = app
        self.channel_id = channel_id
        self.say = say
        self.thread_ts = thread_ts

    async def send_element(self, element_dict: ElementDict):
        if element_dict.get("display") != "inline":
            return

        persisted_file = self.session.files.get(element_dict.get("chainlitKey") or "")
        file: Optional[Union[bytes, str]] = None

        if persisted_file:
            file = str(persisted_file["path"])
        elif file_url := element_dict.get("url"):
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url)
                if response.status_code == 200:
                    file = response.content

        if not file:
            return

        await self.app.client.files_upload_v2(
            channel=self.channel_id,
            thread_ts=self.thread_ts,
            file=file,
            title=element_dict.get("name"),
        )

    async def send_step(self, step_dict: StepDict):
        step_type = step_dict.get("type")
        is_assistant_message = step_type == "assistant_message"
        is_empty_output = not step_dict.get("output")

        if is_empty_output or not is_assistant_message:
            return

        enable_feedback = get_data_layer()
        blocks: List[Dict] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": step_dict["output"]},
            }
        ]
        if enable_feedback:
            current_run = context.current_run
            scorable_id = current_run.id if current_run else step_dict.get("id")
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "action_id": "thumbdown",
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": ":thumbsdown:",
                            },
                            "value": scorable_id,
                        },
                        {
                            "action_id": "thumbup",
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": ":thumbsup:",
                            },
                            "value": scorable_id,
                        },
                    ],
                }
            )
        await self.say(
            text=step_dict["output"], blocks=blocks, thread_ts=self.thread_ts
        )

    async def update_step(self, step_dict: StepDict):
        is_assistant_message = step_dict["type"] == "assistant_message"

        if not is_assistant_message:
            return

        await self.send_step(step_dict)


slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)


def init_slack_context(
    session: HTTPSession,
    slack_channel_id: str,
    event,
    say,
    thread_ts: Optional[str] = None,
) -> ChainlitContext:
    emitter = SlackEmitter(
        session=session,
        app=slack_app,
        channel_id=slack_channel_id,
        say=say,
        thread_ts=thread_ts,
    )
    context = ChainlitContext(session=session, emitter=emitter)
    context_var.set(context)
    user_session.set("slack_event", event)
    user_session.set(
        "fetch_slack_message_history",
        partial(
            fetch_message_history, channel_id=slack_channel_id, thread_ts=thread_ts
        ),
    )
    return context


slack_app_handler = AsyncSlackRequestHandler(slack_app)

users_by_slack_id: Dict[str, Union[User, PersistedUser]] = {}

USER_PREFIX = "slack_"


def clean_content(message: str):
    cleaned_text = re.sub(r"<@[\w]+>", "", message).strip()
    return cleaned_text


async def get_user(slack_user_id: str):
    if slack_user_id in users_by_slack_id:
        return users_by_slack_id[slack_user_id]

    slack_user = await slack_app.client.users_info(user=slack_user_id)
    slack_user_profile = slack_user["user"]["profile"]

    user_identifier = slack_user_profile.get("email") or slack_user_id
    user = User(identifier=USER_PREFIX + user_identifier, metadata=slack_user_profile)

    users_by_slack_id[slack_user_id] = user

    if data_layer := get_data_layer():
        try:
            persisted_user = await data_layer.create_user(user)
            if persisted_user:
                users_by_slack_id[slack_user_id] = persisted_user
        except Exception as e:
            logger.error(f"Error creating user: {e}")

    return users_by_slack_id[slack_user_id]


async def fetch_message_history(
    channel_id: str, thread_ts: Optional[str] = None, limit=30
):
    if not thread_ts:
        result = await slack_app.client.conversations_history(
            channel=channel_id, limit=limit
        )
    else:
        result = await slack_app.client.conversations_replies(
            channel=channel_id, ts=thread_ts, limit=limit
        )
    if result["ok"]:
        messages = result["messages"]
        return messages
    else:
        raise Exception(f"Failed to fetch messages: {result['error']}")


async def download_slack_file(url, token):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            return None


async def download_slack_files(session: HTTPSession, files, token):
    download_coros = [
        download_slack_file(file.get("url_private"), token) for file in files
    ]
    file_bytes_list = await asyncio.gather(*download_coros)
    file_refs = []
    for idx, file_bytes in enumerate(file_bytes_list):
        if file_bytes:
            name = files[idx].get("name")
            mime_type = files[idx].get("mimetype")
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


async def process_slack_message(
    event,
    say,
    thread_id: str,
    thread_name: Optional[str] = None,
    bind_thread_to_user=False,
    thread_ts: Optional[str] = None,
):
    user = await get_user(event["user"])

    channel_id = event["channel"]

    text = event.get("text")
    slack_files = event.get("files", [])

    session_id = str(uuid.uuid4())
    session = HTTPSession(
        id=session_id,
        thread_id=thread_id,
        user=user,
        client_type="slack",
    )

    ctx = init_slack_context(
        session=session,
        slack_channel_id=channel_id,
        event=event,
        say=say,
        thread_ts=thread_ts,
    )

    file_elements = await download_slack_files(
        session, slack_files, slack_app.client.token
    )

    if on_chat_start := config.code.on_chat_start:
        await on_chat_start()

    msg = Message(
        content=clean_content(text),
        elements=file_elements,
        type="user_message",
        author=user.metadata.get("real_name"),
    )

    await msg.send()

    if on_message := config.code.on_message:
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
                name=thread_name or msg.content,
                metadata=ctx.session.to_persistable(),
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"Error updating thread: {e}")

    await ctx.session.delete()


@slack_app.event("app_home_opened")
async def handle_app_home_opened(event, say):
    pass


@slack_app.event("app_mention")
async def handle_app_mentions(event, say):
    thread_ts = event.get("thread_ts", event["ts"])
    thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_ts))

    await process_slack_message(event, say, thread_id=thread_id, thread_ts=thread_ts)


@slack_app.event("message")
async def handle_message(message, say):
    thread_ts = message.get("thread_ts", message["ts"])
    thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_ts))

    await process_slack_message(
        event=message,
        say=say,
        thread_id=thread_id,
        bind_thread_to_user=True,
        thread_ts=thread_ts,
    )


@slack_app.block_action("thumbdown")
async def thumb_down(ack, context, body):
    await ack()
    step_id = body["actions"][0]["value"]

    if data_layer := get_data_layer():
        feedback = Feedback(forId=step_id, value=0)
        await data_layer.upsert_feedback(feedback)

    text = body["message"]["text"]
    blocks = body["message"]["blocks"]
    updated_blocks = [block for block in blocks if block["type"] != "actions"]
    updated_blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":thumbsdown: Feedback received."},
        }
    )
    await context.client.chat_update(
        channel=body["channel"]["id"],
        ts=body["container"]["message_ts"],
        text=text,
        blocks=updated_blocks,
    )


@slack_app.block_action("thumbup")
async def thumb_up(ack, context, body):
    await ack()
    step_id = body["actions"][0]["value"]

    if data_layer := get_data_layer():
        feedback = Feedback(forId=step_id, value=1)
        await data_layer.upsert_feedback(feedback)

    text = body["message"]["text"]
    blocks = body["message"]["blocks"]
    updated_blocks = [block for block in blocks if block["type"] != "actions"]
    updated_blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":thumbsup: Feedback received."},
        }
    )
    await context.client.chat_update(
        channel=body["channel"]["id"],
        ts=body["container"]["message_ts"],
        text=text,
        blocks=updated_blocks,
    )
