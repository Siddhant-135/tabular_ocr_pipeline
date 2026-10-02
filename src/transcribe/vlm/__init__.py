from transcribe.vlm.base import VLMBackend


def get_backend(name: str, model: str | None = None) -> VLMBackend:
    if name == "mock":
        from transcribe.vlm.mock import MockBackend

        return MockBackend()
    if name == "mlx":
        from transcribe.vlm.mlx import MLXBackend

        return MLXBackend(model) if model else MLXBackend()
    raise ValueError(f"unknown VLM backend: {name!r} (expected 'mlx' or 'mock')")


__all__ = ["VLMBackend", "get_backend"]
