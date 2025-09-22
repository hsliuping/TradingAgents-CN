"""OpenTelemetry CrewAI instrumentation"""
from opentelemetry.instrumentation.crewai.version import __version__
from opentelemetry.instrumentation.crewai.instrumentation import CrewAIInstrumentor

__all__ = ["CrewAIInstrumentor", "__version__"]
