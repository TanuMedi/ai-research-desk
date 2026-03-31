import json

import config


class LLMClient:
    """Async LLM wrapper supporting Claude (Anthropic) and OpenAI."""

    def __init__(self, temperature: float = 0.0) -> None:
        self.provider = config.LLM_PROVIDER.lower()
        self.temperature = temperature
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
        print(f"[LLMClient] provider={self.provider} model={self._model} temperature={self.temperature} max_tokens={config.LLM_MAX_TOKENS}")

    async def complete(self, prompt: str) -> str:
        """Send a prompt and return the text response."""
        if self.provider == "claude":
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=self.temperature,
            )
            return response.choices[0].message.content


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
