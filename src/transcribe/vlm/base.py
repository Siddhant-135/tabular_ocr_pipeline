from pathlib import Path
from typing import Protocol


class VLMBackend(Protocol):
    name: str

    def generate(self, image: Path, prompt: str, max_tokens: int = 128) -> str:
        """Return the raw text answer of the model for one image + prompt."""
        ...
