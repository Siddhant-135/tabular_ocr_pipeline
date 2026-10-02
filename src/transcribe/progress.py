"""Timestamped terminal progress, so it is always visible what is running and where it is."""

import time

_START = time.time()


def _fmt(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')} +{_fmt(time.time() - _START)}] {msg}", flush=True)


def stage(n: int, total: int, name: str, detail: str = "") -> None:
    log(f"=== stage {n}/{total}: {name}" + (f" ({detail})" if detail else ""))


class Progress:
    """Counts steps; logs every `every` steps and at the end, with elapsed time and ETA."""

    def __init__(self, label: str, total: int, every: int = 5):
        self.label, self.total, self.every = label, total, every
        self.done = 0
        self.start = time.time()

    def step(self, n: int = 1) -> None:
        self.done += n
        if self.done % self.every and self.done != self.total:
            return
        elapsed = time.time() - self.start
        eta = elapsed / self.done * (self.total - self.done)
        tail = f"in {_fmt(elapsed)}" if self.done == self.total else f"{_fmt(elapsed)}, ~{_fmt(eta)} left"
        log(f"{self.label}: {self.done}/{self.total} done ({tail})")

    def elapsed(self) -> str:
        return _fmt(time.time() - self.start)
