from __future__ import annotations

from threading import Event

from Core.cli.instance import InstanceDriver
from Core.presentation.runtime.startup import create_loading_application
from universal_gui.contracts import Request


def main(core: CoreRuntime, instance: InstanceDriver, preview: bool, activation: Event) -> int:
    application, startup = create_loading_application(preview, core, instance if core is None else None, activation)
    return application.run()
