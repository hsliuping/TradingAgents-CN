from enum import Enum

SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY = "suppress_language_model_instrumentation"


class Meters:
    LLM_GENERATION_CHOICES = "gen_ai.client.generation.choices"
    LLM_TOKEN_USAGE = "gen_ai.client.token.usage"
    LLM_OPERATION_DURATION = "gen_ai.client.operation.duration"
    LLM_COMPLETIONS_EXCEPTIONS = "llm.openai.chat_completions.exceptions"
    LLM_STREAMING_TIME_TO_FIRST_TOKEN = (
        "llm.openai.chat_completions.streaming_time_to_first_token"
    )
    LLM_STREAMING_TIME_TO_GENERATE = (
        "llm.openai.chat_completions.streaming_time_to_generate"
    )
    LLM_EMBEDDINGS_EXCEPTIONS = "llm.openai.embeddings.exceptions"
    LLM_EMBEDDINGS_VECTOR_SIZE = "llm.openai.embeddings.vector_size"
    LLM_IMAGE_GENERATIONS_EXCEPTIONS = "llm.openai.image_generations.exceptions"
    LLM_ANTHROPIC_COMPLETION_EXCEPTIONS = "llm.anthropic.completion.exceptions"

    PINECONE_DB_QUERY_DURATION = "db.pinecone.query.duration"
    PINECONE_DB_QUERY_SCORES = "db.pinecone.query.scores"
    PINECONE_DB_USAGE_READ_UNITS = "db.pinecone.usage.read_units"
    PINECONE_DB_USAGE_WRITE_UNITS = "db.pinecone.usage_write_units"

    LLM_WATSONX_COMPLETIONS_DURATION = "llm.watsonx.completions.duration"
    LLM_WATSONX_COMPLETIONS_EXCEPTIONS = "llm.watsonx.completions.exceptions"
    LLM_WATSONX_COMPLETIONS_RESPONSES = "llm.watsonx.completions.responses"
    LLM_WATSONX_COMPLETIONS_TOKENS = "llm.watsonx.completions.tokens"


class SpanAttributes:
    # Semantic Conventions for LLM requests, this needs to be removed after
    # OpenTelemetry Semantic Conventions support Gen AI.
    # Issue at https://github.com/open-telemetry/opentelemetry-python/issues/3868
    # Refer to https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md
    # for more detail for LLM spans from OpenTelemetry Community.
    LLM_SYSTEM = "gen_ai.system"
    LLM_REQUEST_MODEL = "gen_ai.request.model"
    LLM_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    LLM_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    LLM_REQUEST_TOP_P = "gen_ai.request.top_p"
    LLM_PROMPTS = "gen_ai.prompt"
    LLM_COMPLETIONS = "gen_ai.completion"
    LLM_RESPONSE_MODEL = "gen_ai.response.model"
    LLM_USAGE_COMPLETION_TOKENS = "gen_ai.usage.completion_tokens"
    LLM_USAGE_PROMPT_TOKENS = "gen_ai.usage.prompt_tokens"
    LLM_USAGE_CACHE_CREATION_INPUT_TOKENS = "gen_ai.usage.cache_creation_input_tokens"
    LLM_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read_input_tokens"
    LLM_TOKEN_TYPE = "gen_ai.token.type"
    # To be added
    # LLM_RESPONSE_ID = "gen_ai.response.id"

    # LLM
    LLM_REQUEST_TYPE = "llm.request.type"
    LLM_USAGE_TOTAL_TOKENS = "llm.usage.total_tokens"
    LLM_USAGE_TOKEN_TYPE = "llm.usage.token_type"
    LLM_USER = "llm.user"
    LLM_HEADERS = "llm.headers"
    LLM_TOP_K = "llm.top_k"
    LLM_IS_STREAMING = "llm.is_streaming"
    LLM_FREQUENCY_PENALTY = "llm.frequency_penalty"
    LLM_PRESENCE_PENALTY = "llm.presence_penalty"
    LLM_CHAT_STOP_SEQUENCES = "llm.chat.stop_sequences"
    LLM_REQUEST_FUNCTIONS = "llm.request.functions"
    LLM_REQUEST_REPETITION_PENALTY = "llm.request.repetition_penalty"
    LLM_RESPONSE_FINISH_REASON = "llm.response.finish_reason"
    LLM_RESPONSE_STOP_REASON = "llm.response.stop_reason"
    LLM_CONTENT_COMPLETION_CHUNK = "llm.content.completion.chunk"

    # OpenAI
    LLM_OPENAI_RESPONSE_SYSTEM_FINGERPRINT = "gen_ai.openai.system_fingerprint"
    LLM_OPENAI_API_BASE = "gen_ai.openai.api_base"
    LLM_OPENAI_API_VERSION = "gen_ai.openai.api_version"
    LLM_OPENAI_API_TYPE = "gen_ai.openai.api_type"

    # Haystack
    HAYSTACK_OPENAI_CHAT = "haystack.openai.chat"
    HAYSTACK_OPENAI_COMPLETION = "haystack.openai.completion"

    # Vector DB
    VECTOR_DB_VENDOR = "db.system"
    VECTOR_DB_OPERATION = "db.operation"
    VECTOR_DB_QUERY_TOP_K = "db.vector.query.top_k"

    # Pinecone
    PINECONE_USAGE_READ_UNITS = "pinecone.usage.read_units"
    PINECONE_USAGE_WRITE_UNITS = "pinecone.usage.write_units"
    PINECONE_QUERY_FILTER = "pinecone.query.filter"
    PINECONE_QUERY_ID = "pinecone.query.id"
    PINECONE_QUERY_INCLUDE_METADATA = "pinecone.query.include_metadata"
    PINECONE_QUERY_INCLUDE_VALUES = "pinecone.query.include_values"
    PINECONE_QUERY_NAMESPACE = "pinecone.query.namespace"
    PINECONE_QUERY_QUERIES = "pinecone.query.queries"
    PINECONE_QUERY_TOP_K = "pinecone.query.top_k"

    # LLM Workflows
    TRACELOOP_SPAN_KIND = "traceloop.span.kind"
    TRACELOOP_WORKFLOW_NAME = "traceloop.workflow.name"
    TRACELOOP_ENTITY_NAME = "traceloop.entity.name"
    TRACELOOP_ENTITY_PATH = "traceloop.entity.path"
    TRACELOOP_ENTITY_VERSION = "traceloop.entity.version"
    TRACELOOP_ENTITY_INPUT = "traceloop.entity.input"
    TRACELOOP_ENTITY_OUTPUT = "traceloop.entity.output"
    TRACELOOP_ASSOCIATION_PROPERTIES = "traceloop.association.properties"

    # Prompts
    TRACELOOP_PROMPT_MANAGED = "traceloop.prompt.managed"
    TRACELOOP_PROMPT_KEY = "traceloop.prompt.key"
    TRACELOOP_PROMPT_VERSION = "traceloop.prompt.version"
    TRACELOOP_PROMPT_VERSION_NAME = "traceloop.prompt.version_name"
    TRACELOOP_PROMPT_VERSION_HASH = "traceloop.prompt.version_hash"
    TRACELOOP_PROMPT_TEMPLATE = "traceloop.prompt.template"
    TRACELOOP_PROMPT_TEMPLATE_VARIABLES = "traceloop.prompt.template_variables"

    # Deprecated
    TRACELOOP_CORRELATION_ID = "traceloop.correlation.id"

    # Watson/genai LLM
    LLM_DECODING_METHOD = "llm.watsonx.decoding_method"
    LLM_RANDOM_SEED = "llm.watsonx.random_seed"
    LLM_MAX_NEW_TOKENS = "llm.watsonx.max_new_tokens"
    LLM_MIN_NEW_TOKENS = "llm.watsonx.min_new_tokens"
    LLM_REPETITION_PENALTY = "llm.watsonx.repetition_penalty"

    # Chroma db
    CHROMADB_ADD_IDS_COUNT = "db.chroma.add.ids_count"
    CHROMADB_ADD_EMBEDDINGS_COUNT = "db.chroma.add.embeddings_count"
    CHROMADB_ADD_METADATAS_COUNT = "db.chroma.add.metadatas_count"
    CHROMADB_ADD_DOCUMENTS_COUNT = "db.chroma.add.documents_count"
    CHROMADB_DELETE_IDS_COUNT = "db.chroma.delete.ids_count"
    CHROMADB_DELETE_WHERE = "db.chroma.delete.where"
    CHROMADB_DELETE_WHERE_DOCUMENT = "db.chroma.delete.where_document"
    CHROMADB_GET_IDS_COUNT = "db.chroma.get.ids_count"
    CHROMADB_GET_INCLUDE = "db.chroma.get.include"
    CHROMADB_GET_LIMIT = "db.chroma.get.limit"
    CHROMADB_GET_OFFSET = "db.chroma.get.offset"
    CHROMADB_GET_WHERE = "db.chroma.get.where"
    CHROMADB_GET_WHERE_DOCUMENT = "db.chroma.get.where_document"
    CHROMADB_MODIFY_NAME = "db.chroma.modify.name"
    CHROMADB_PEEK_LIMIT = "db.chroma.peek.limit"
    CHROMADB_QUERY_EMBEDDINGS_COUNT = "db.chroma.query.embeddings_count"
    CHROMADB_QUERY_TEXTS_COUNT = "db.chroma.query.texts_count"
    CHROMADB_QUERY_N_RESULTS = "db.chroma.query.n_results"
    CHROMADB_QUERY_INCLUDE = "db.chroma.query.include"
    CHROMADB_QUERY_SEGMENT_QUERY_COLLECTION_ID = (
        "db.chroma.query.segment._query.collection_id"
    )
    CHROMADB_QUERY_WHERE = "db.chroma.query.where"
    CHROMADB_QUERY_WHERE_DOCUMENT = "db.chroma.query.where_document"
    CHROMADB_UPDATE_DOCUMENTS_COUNT = "db.chroma.update.documents_count"
    CHROMADB_UPDATE_EMBEDDINGS_COUNT = "db.chroma.update.embeddings_count"
    CHROMADB_UPDATE_IDS_COUNT = "db.chroma.update.ids_count"
    CHROMADB_UPDATE_METADATAS_COUNT = "db.chroma.update.metadatas_count"
    CHROMADB_UPSERT_DOCUMENTS_COUNT = "db.chroma.upsert.documents_count"
    CHROMADB_UPSERT_EMBEDDINGS_COUNT = "db.chroma.upsert.embeddings_count"
    CHROMADB_UPSERT_METADATAS_COUNT = "db.chroma.upsert.metadatas_count"

    # Milvus
    MILVUS_DELETE_COLLECTION_NAME = "db.milvus.delete.collection_name"
    MILVUS_DELETE_FILTER = "db.milvus.delete.filter"
    MILVUS_DELETE_IDS_COUNT = "db.milvus.delete.ids_count"
    MILVUS_DELETE_PARTITION_NAME = "db.milvus.delete.partition_name"
    MILVUS_DELETE_TIMEOUT = "db.milvus.delete.timeout"
    MILVUS_GET_COLLECTION_NAME = "db.milvus.get.collection_name"
    MILVUS_GET_PARTITION_NAMES_COUNT = "db.milvus.get.partition_names_count"
    MILVUS_GET_IDS_COUNT = "db.milvus.get.ids_count"
    MILVUS_GET_OUTPUT_FIELDS_COUNT = "db.milvus.get.output_fields_count"
    MILVUS_GET_TIMEOUT = "db.milvus.get.timeout"
    MILVUS_CREATE_COLLECTION_NAME = "db.milvus.create_collection.collection_name"
    MILVUS_CREATE_COLLECTION_DIMENSION = "db.milvus.create_collection.dimension"
    MILVUS_CREATE_COLLECTION_PRIMARY_FIELD = "db.milvus.create_collection.primary_field"
    MILVUS_CREATE_COLLECTION_METRIC_TYPE = "db.milvus.create_collection.metric_type"
    MILVUS_CREATE_COLLECTION_TIMEOUT = "db.milvus.create_collection.timeout"
    MILVUS_CREATE_COLLECTION_ID_TYPE = "db.milvus.create_collection.id_type"
    MILVUS_CREATE_COLLECTION_VECTOR_FIELD = "db.milvus.create_collection.vector_field"
    MILVUS_INSERT_COLLECTION_NAME = "db.milvus.insert.collection_name"
    MILVUS_INSERT_DATA_COUNT = "db.milvus.insert.data_count"
    MILVUS_INSERT_PARTITION_NAME = "db.milvus.insert.partition_name"
    MILVUS_INSERT_TIMEOUT = "db.milvus.insert.timeout"
    MILVUS_QUERY_COLLECTION_NAME = "db.milvus.query.collection_name"
    MILVUS_QUERY_FILTER = "db.milvus.query.filter"
    MILVUS_QUERY_IDS_COUNT = "db.milvus.query.ids_count"
    MILVUS_QUERY_LIMIT = "db.milvus.query.limit"
    MILVUS_QUERY_OUTPUT_FIELDS_COUNT = "db.milvus.query.output_fields_count"
    MILVUS_QUERY_PARTITION_NAMES_COUNT = "db.milvus.query.partition_names_count"
    MILVUS_QUERY_TIMEOUT = "db.milvus.query.timeout"
    MILVUS_SEARCH_ANNS_FIELD = "db.milvus.search.anns_field"
    MILVUS_SEARCH_COLLECTION_NAME = "db.milvus.search.collection_name"
    MILVUS_SEARCH_DATA_COUNT = "db.milvus.search.data_count"
    MILVUS_SEARCH_FILTER = "db.milvus.search.filter"
    MILVUS_SEARCH_LIMIT = "db.milvus.search.limit"
    MILVUS_SEARCH_OUTPUT_FIELDS_COUNT = "db.milvus.search.output_fields_count"
    MILVUS_SEARCH_PARTITION_NAMES_COUNT = "db.milvus.search.partition_names_count"
    MILVUS_SEARCH_SEARCH_PARAMS = "db.milvus.search.search_params"
    MILVUS_SEARCH_TIMEOUT = "db.milvus.search.timeout"
    MILVUS_SEARCH_PARTITION_NAMES = "db.milvus.search.partition_names"
    MILVUS_SEARCH_RESULT_COUNT = "db.milvus.search.result_count"
    MILVUS_SEARCH_QUERY_VECTOR_DIMENSION = "db.milvus.search.query_vector_dimension"
    MILVUS_SEARCH_ANNSEARCH_REQUEST = "db.milvus.search.annsearch_request"
    MILVUS_SEARCH_RANKER_TYPE = "db.milvus.search.ranker_type"
    MILVUS_UPSERT_COLLECTION_NAME = "db.milvus.upsert.collection_name"
    MILVUS_UPSERT_DATA_COUNT = "db.milvus.upsert.data_count"
    MILVUS_UPSERT_PARTITION_NAME = "db.milvus.upsert.partition_name"
    MILVUS_UPSERT_TIMEOUT = "db.milvus.upsert.timeout"

    # Qdrant
    QDRANT_SEARCH_COLLECTION_NAME = "qdrant.search.collection_name"
    QDRANT_SEARCH_BATCH_COLLECTION_NAME = "qdrant.search_batch.collection_name"
    QDRANT_SEARCH_BATCH_REQUESTS_COUNT = "qdrant.search_batch.requests_count"
    QDRANT_UPLOAD_COLLECTION_NAME = "qdrant.upload_collection.collection_name"
    QDRANT_UPLOAD_POINTS_COUNT = "qdrant.upload_collection.points_count"
    QDRANT_UPSERT_COLLECTION_NAME = "qdrant.upsert.collection_name"
    QDRANT_UPSERT_POINTS_COUNT = "qdrant.upsert.points_count"

    # Marqo
    MARQO_SEARCH_QUERY = "db.marqo.search.query"
    MARQO_SEARCH_PROCESSING_TIME = "db.marqo.search.processing_time"
    MARQO_DELETE_DOCUMENTS_STATUS = "db.marqo.delete_documents.status"

    # MCP
    MCP_METHOD_NAME = "mcp.method.name"
    MCP_REQUEST_ARGUMENT = "mcp.request.argument"
    MCP_REQUEST_ID = "mcp.request.id"
    MCP_SESSION_INIT_OPTIONS = "mcp.session.init_options"
    MCP_RESPONSE_VALUE = "mcp.response.value"


class Events(Enum):
    DB_QUERY_EMBEDDINGS = "db.query.embeddings"
    DB_QUERY_RESULT = "db.query.result"
    DB_SEARCH_EMBEDDINGS = "db.search.embeddings"
    DB_SEARCH_RESULT = "db.search.result"


class EventAttributes(Enum):
    # Query Embeddings
    DB_QUERY_EMBEDDINGS_VECTOR = "db.query.embeddings.vector"

    # Query Result (canonical format)
    DB_QUERY_RESULT_ID = "db.query.result.id"
    DB_QUERY_RESULT_SCORE = "db.query.result.score"
    DB_QUERY_RESULT_DISTANCE = "db.query.result.distance"
    DB_QUERY_RESULT_METADATA = "db.query.result.metadata"
    DB_QUERY_RESULT_VECTOR = "db.query.result.vector"
    DB_QUERY_RESULT_DOCUMENT = "db.query.result.document"

    # SEARCH
    DB_SEARCH_EMBEDDINGS_VECTOR = "db.search.embeddings.vector"

    DB_SEARCH_RESULT_QUERY_ID = "db.search.query.id"  # For multi-vector searches
    DB_SEARCH_RESULT_ID = "db.search.result.id"
    DB_SEARCH_RESULT_SCORE = "db.search.result.score"
    DB_SEARCH_RESULT_DISTANCE = "db.search.result.distance"
    DB_SEARCH_RESULT_ENTITY = "db.search.result.entity"


class LLMRequestTypeValues(Enum):
    COMPLETION = "completion"
    CHAT = "chat"
    RERANK = "rerank"
    EMBEDDING = "embedding"
    UNKNOWN = "unknown"


class TraceloopSpanKindValues(Enum):
    WORKFLOW = "workflow"
    TASK = "task"
    AGENT = "agent"
    TOOL = "tool"
    UNKNOWN = "unknown"
