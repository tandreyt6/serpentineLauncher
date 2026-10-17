from Core.application.diagnostics import diagnostic

from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock

from Core.application.tasks import Cancellation
from Core.configuration.settings import THEME_HEALTH_FILENAME, THEME_HEALTH_BYTES


@dataclass(frozen=True)
class ThemeHealth:
    failures: tuple[tuple[str, str], ...] = ()
    attempt: str = ""

    def recover_interrupted(self, protected: tuple[str, ...]) -> "ThemeHealth":
        failures = dict(self.failures)
        if self.attempt and self.attempt not in protected:
            failures[self.attempt] = "Theme activation was interrupted before the interface became ready."
        return ThemeHealth(tuple(failures.items()))


class ThemeHealthDriver:
    def __init__(self, root: Path):
        self.path = root / THEME_HEALTH_FILENAME
        self.lock = Lock()

    def read(self) -> ThemeHealth:
        with self.lock:
            if not self.path.exists():
                return ThemeHealth()
            with self.path.open('rb') as stream:
                content = stream.read(THEME_HEALTH_BYTES + 1)
            if len(content) > THEME_HEALTH_BYTES:
                raise ValueError(diagnostic('theme_health.theme.health.journal.exceeds.size.limit'))
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError(diagnostic('theme_health.invalid.theme.health.journal'))
            failures = data.get('failures', {})
            attempt = data.get('attempt', '')
            if not isinstance(failures, dict) or not isinstance(attempt, str):
                raise ValueError(diagnostic('theme_health.invalid.theme.health.journal'))
            if any(not isinstance(key, str) or not isinstance(reason, str) for key, reason in failures.items()):
                raise ValueError(diagnostic('theme_health.invalid.theme.failure.record'))
            return ThemeHealth(tuple(failures.items()), attempt)

    def write(self, snapshot: ThemeHealth) -> ThemeHealth:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps({'failures': dict(snapshot.failures), 'attempt': snapshot.attempt}, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(self.path)
            return snapshot


class ThemeHealthOperation:
    def __init__(self, driver: ThemeHealthDriver, snapshot: ThemeHealth | None = None):
        self.driver, self.snapshot = driver, snapshot

    def run(self, task_id: str, cancellation: Cancellation) -> ThemeHealth:
        cancellation.check()
        return self.driver.read() if self.snapshot is None else self.driver.write(self.snapshot)
