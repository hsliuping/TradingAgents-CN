try:
    import openai
    import openai.resources
except ImportError:
    raise ModuleNotFoundError("Please install the Open AI SDK to use this feature: 'pip install openai'")

from posthog.ai.openai.openai import WrappedBeta, WrappedChat, WrappedEmbeddings
from posthog.ai.openai.openai_async import WrappedBeta as AsyncWrappedBeta
from posthog.ai.openai.openai_async import WrappedChat as AsyncWrappedChat
from posthog.ai.openai.openai_async import WrappedEmbeddings as AsyncWrappedEmbeddings
from posthog.client import Client as PostHogClient


class AzureOpenAI(openai.AzureOpenAI):
    """
    A wrapper around the Azure OpenAI SDK that automatically sends LLM usage events to PostHog.
    """

    _ph_client: PostHogClient

    def __init__(self, posthog_client: PostHogClient, **kwargs):
        super().__init__(**kwargs)
        self._ph_client = posthog_client
        self.chat = WrappedChat(self)
        self.embeddings = WrappedEmbeddings(self)
        self.beta = WrappedBeta(self)


class AsyncAzureOpenAI(openai.AsyncAzureOpenAI):
    """
    A wrapper around the Azure OpenAI SDK that automatically sends LLM usage events to PostHog.
    """

    _ph_client: PostHogClient

    def __init__(self, posthog_client: PostHogClient, **kwargs):
        super().__init__(**kwargs)
        self._ph_client = posthog_client
        self.chat = AsyncWrappedChat(self)
        self.embeddings = AsyncWrappedEmbeddings(self)
        self.beta = AsyncWrappedBeta(self)
