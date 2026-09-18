from onecode.models.providers.openai_provider import OpenAIProvider
from onecode.models.provider import ProviderRegistry


class OpenAICustomProvider(OpenAIProvider):
    name = "openai-custom"


ProviderRegistry.register("openai-custom", OpenAICustomProvider)
