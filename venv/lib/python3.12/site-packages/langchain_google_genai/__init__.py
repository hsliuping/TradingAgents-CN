"""**LangChain Google Generative AI Integration**

This module integrates Google's Generative AI models, specifically the Gemini series, with the LangChain framework. It provides classes for interacting with chat models and generating embeddings, leveraging Google's advanced AI capabilities.

**Chat Models**

The ``ChatGoogleGenerativeAI`` class is the primary interface for interacting with Google's Gemini chat models. It allows users to send and receive messages using a specified Gemini model, suitable for various conversational AI applications.

**LLMs**

The ``GoogleGenerativeAI`` class is the primary interface for interacting with Google's Gemini LLMs. It allows users to generate text using a specified Gemini model.

**Embeddings**

The ``GoogleGenerativeAIEmbeddings`` class provides functionalities to generate embeddings using Google's models.
These embeddings can be used for a range of NLP tasks, including semantic analysis, similarity comparisons, and more.

**Installation**

To install the package, use pip:

.. code-block:: python
    pip install -U langchain-google-genai

**Using Chat Models**

After setting up your environment with the required API key, you can interact with the Google Gemini models.

.. code-block:: python

    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model="gemini-pro")
    llm.invoke("Sing a ballad of LangChain.")

**Using LLMs**

The package also supports generating text with Google's models.

.. code-block:: python

    from langchain_google_genai import GoogleGenerativeAI

    llm = GoogleGenerativeAI(model="gemini-pro")
    llm.invoke("Once upon a time, a library called LangChain")

**Embedding Generation**

The package also supports creating embeddings with Google's models, useful for textual similarity and other NLP applications.

.. code-block:: python

    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    embeddings.embed_query("hello, world!")

"""  # noqa: E501

from langchain_google_genai._enums import HarmBlockThreshold, HarmCategory, Modality
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings
from langchain_google_genai.genai_aqa import (
    AqaInput,
    AqaOutput,
    GenAIAqa,
)
from langchain_google_genai.google_vector_store import (
    DoesNotExistsException,
    GoogleVectorStore,
)
from langchain_google_genai.llms import GoogleGenerativeAI

__all__ = [
    "AqaInput",
    "AqaOutput",
    "ChatGoogleGenerativeAI",
    "DoesNotExistsException",
    "GenAIAqa",
    "GoogleGenerativeAIEmbeddings",
    "GoogleGenerativeAI",
    "GoogleVectorStore",
    "HarmBlockThreshold",
    "HarmCategory",
    "Modality",
    "DoesNotExistsException",
]
