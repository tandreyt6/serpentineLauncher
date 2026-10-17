from dataclasses import dataclass


@dataclass(frozen=True)
class CliRequest:
    action: str = "activate"
    key: str = ""
    value: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    format: str = "text"
    preview: bool = False


@dataclass(frozen=True)
class CliResponse:
    code: int = 0
    stdout: str = ""
    stderr: str = ""
