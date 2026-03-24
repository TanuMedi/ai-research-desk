import config


class LLMClient:
    """Async LLM wrapper supporting Claude (Anthropic) and OpenAI."""

    def __init__(self) -> None:
        self.provider = config.LLM_PROVIDER.lower()
        if self.provider == "claude":
            import anthropic
            self._client = anthropic.AsyncAnthropic()
            self._model = config.CLAUDE_MODEL
        elif self.provider == "openai":
            import openai
            self._client = openai.AsyncOpenAI()
            self._model = config.OPENAI_MODEL
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{self.provider}'. Set LLM_PROVIDER=claude or LLM_PROVIDER=openai."
            )

    async def complete(self, prompt: str) -> str:
        """Send a prompt and return the text response."""
        if self.provider == "claude":
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            return response.choices[0].message.content
