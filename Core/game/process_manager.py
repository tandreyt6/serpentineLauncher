from Core.application.diagnostics import diagnostic
from time import monotonic, sleep

from Core.application.contracts import CoreError
from Core.game.processes import ManagedProcess, ProcessAdapter, ProcessSpec
from Core.application.tasks import Cancellation


class ProcessDriver:
    def __init__(self, adapter: ProcessAdapter) -> None:
        self._adapter = adapter

    def spawn(self, spec: ProcessSpec) -> ManagedProcess:
        return self._adapter.spawn(spec)

    def execute(self, spec: ProcessSpec, cancellation: Cancellation, timeout: float, interval: float) -> None:
        cancellation.check()
        process = self.spawn(spec)
        started = monotonic()
        try:
            while process.poll() is None:
                cancellation.check_cancelled()
                if monotonic() - started >= timeout:
                    raise CoreError(diagnostic('process_manager.installer.processor.timed.out.see', spec.log_path))
                sleep(interval)
            cancellation.check_cancelled()
            if process.wait() != 0:
                raise CoreError(diagnostic('process_manager.installer.processor.failed.see', spec.log_path))
        finally:
            process.dispose()
        cancellation.check()

    def close(self) -> None:
        pass
