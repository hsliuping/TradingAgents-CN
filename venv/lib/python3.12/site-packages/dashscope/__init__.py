# Copyright (c) Alibaba, Inc. and its affiliates.

import logging
from logging import NullHandler

from dashscope.aigc.code_generation import CodeGeneration
from dashscope.aigc.conversation import Conversation, History, HistoryItem
from dashscope.aigc.generation import AioGeneration, Generation
from dashscope.aigc.image_synthesis import ImageSynthesis
from dashscope.aigc.multimodal_conversation import MultiModalConversation
from dashscope.aigc.video_synthesis import VideoSynthesis
from dashscope.app.application import Application
from dashscope.assistants import Assistant, AssistantList, Assistants
from dashscope.assistants.assistant_types import AssistantFile, DeleteResponse
from dashscope.audio.asr.transcription import Transcription
from dashscope.audio.tts.speech_synthesizer import SpeechSynthesizer
from dashscope.common.api_key import save_api_key
from dashscope.common.env import (api_key, api_key_file_path,
                                  base_http_api_url, base_websocket_api_url)
from dashscope.customize.deployments import Deployments
from dashscope.customize.finetunes import FineTunes
from dashscope.embeddings.batch_text_embedding import BatchTextEmbedding
from dashscope.embeddings.batch_text_embedding_response import \
    BatchTextEmbeddingResponse
from dashscope.embeddings.multimodal_embedding import (
    MultiModalEmbedding, MultiModalEmbeddingItemAudio,
    MultiModalEmbeddingItemImage, MultiModalEmbeddingItemText)
from dashscope.embeddings.text_embedding import TextEmbedding
from dashscope.files import Files
from dashscope.models import Models
from dashscope.nlp.understanding import Understanding
from dashscope.rerank.text_rerank import TextReRank
from dashscope.threads import (MessageFile, Messages, Run, RunList, Runs,
                               RunStep, RunStepList, Steps, Thread,
                               ThreadMessage, ThreadMessageList, Threads)
from dashscope.tokenizers import (Tokenization, Tokenizer, get_tokenizer,
                                  list_tokenizers)

__all__ = [
    base_http_api_url,
    base_websocket_api_url,
    api_key,
    api_key_file_path,
    save_api_key,
    AioGeneration,
    Conversation,
    Generation,
    History,
    HistoryItem,
    ImageSynthesis,
    Transcription,
    Files,
    Deployments,
    FineTunes,
    Models,
    TextEmbedding,
    MultiModalEmbedding,
    MultiModalEmbeddingItemAudio,
    MultiModalEmbeddingItemImage,
    MultiModalEmbeddingItemText,
    SpeechSynthesizer,
    MultiModalConversation,
    BatchTextEmbedding,
    BatchTextEmbeddingResponse,
    Understanding,
    CodeGeneration,
    Tokenization,
    Tokenizer,
    get_tokenizer,
    list_tokenizers,
    Application,
    TextReRank,
    Assistants,
    Threads,
    Messages,
    Runs,
    Assistant,
    ThreadMessage,
    Run,
    Steps,
    AssistantList,
    ThreadMessageList,
    RunList,
    RunStepList,
    Thread,
    DeleteResponse,
    RunStep,
    MessageFile,
    AssistantFile,
    VideoSynthesis,
]

logging.getLogger(__name__).addHandler(NullHandler())
