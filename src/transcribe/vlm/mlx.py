"""Local VLM on Apple Silicon via mlx-vlm (greedy decoding, thinking disabled)."""

from pathlib import Path

DEFAULT_MODEL = "mlx-community/Qwen3.5-9B-MLX-8bit"


class MLXBackend:
    name = "mlx"

    def __init__(self, model: str = DEFAULT_MODEL):
        import time

        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        from transcribe.progress import log

        log(f"loading model {model} ...")
        t = time.time()
        self.model_id = model
        self.model, self.processor = load(model)
        self.config = load_config(model)
        log(f"model loaded in {time.time() - t:.1f}s")

    def generate(self, image: Path, prompt: str, max_tokens: int = 128) -> str:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted = apply_chat_template(
            self.processor, self.config, prompt, num_images=1, enable_thinking=False
        )
        result = generate(
            self.model,
            self.processor,
            formatted,
            image=[str(image)],
            max_tokens=max_tokens,
            temperature=0.0,
            verbose=False,
        )
        return _strip_think(result.text)


def _strip_think(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()
