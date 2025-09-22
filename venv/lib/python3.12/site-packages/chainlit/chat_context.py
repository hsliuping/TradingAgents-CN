from typing import TYPE_CHECKING, Dict, List

from chainlit.context import context

if TYPE_CHECKING:
    from chainlit.message import Message

chat_contexts: Dict[str, List["Message"]] = {}


class ChatContext:
    def get(self) -> List["Message"]:
        if not context.session:
            return []

        if context.session.id not in chat_contexts:
            # Create a new chat context
            chat_contexts[context.session.id] = []

        return chat_contexts[context.session.id].copy()

    def add(self, message: "Message"):
        if not context.session:
            return

        if context.session.id not in chat_contexts:
            chat_contexts[context.session.id] = []

        if message not in chat_contexts[context.session.id]:
            chat_contexts[context.session.id].append(message)

        return message

    def remove(self, message: "Message") -> bool:
        if not context.session:
            return False

        if context.session.id not in chat_contexts:
            return False

        if message in chat_contexts[context.session.id]:
            chat_contexts[context.session.id].remove(message)
            return True

        return False

    def clear(self) -> None:
        if context.session and context.session.id in chat_contexts:
            chat_contexts[context.session.id] = []

    def to_openai(self):
        messages = []
        for message in self.get():
            if message.type == "assistant_message":
                messages.append({"role": "assistant", "content": message.content})
            elif message.type == "user_message":
                messages.append({"role": "user", "content": message.content})
            else:
                messages.append({"role": "system", "content": message.content})

        return messages


chat_context = ChatContext()
