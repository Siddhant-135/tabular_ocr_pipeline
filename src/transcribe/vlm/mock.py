"""Deterministic fake VLM to dry-run the pipeline end to end without a model.

Every 7th row returns a bad phone on the first pass (exercises recheck) and every
13th row stays bad on the retry too (exercises checks_failed).
"""

import json
import re
from pathlib import Path


class MockBackend:
    name = "mock"

    def __init__(self):
        self._seen: set[Path] = set()

    def generate(self, image: Path, prompt: str, max_tokens: int = 128) -> str:
        m = re.search(r"row_(\d+)", image.name)
        row = int(m.group(1)) if m else 0
        if '"phone"' not in prompt and "10 digits" in prompt:
            return "98765432" + f"{row:02d}"
        if '"phone"' not in prompt:
            return ["Ph-11", "Sec49", "Vill", "Ph11", "MHL"][row % 5]

        retry = image in self._seen
        self._seen.add(image)
        phone = "98765432" + f"{row:02d}"
        if (row % 7 == 0 and not retry) or row % 13 == 0:
            phone = phone[:-1]
        return json.dumps({"name": "Mock Kaur", "location": "Ph-11", "phone": phone})
