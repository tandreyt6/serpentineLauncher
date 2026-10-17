import re


def version_key(value: str) -> tuple:
    match = re.match(r"^(\d+(?:\.\d+)*)", value)
    numbers = tuple(int(part) for part in match.group().split(".")) if match else ()
    suffix = value[match.end():].lower() if match else value.lower()
    stage = 3 if not suffix else 2 if suffix.startswith(("-rc", " rc")) else 1 if suffix.startswith(("-pre", " pre")) else 0
    tokens = tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.findall(r"\d+|\D+", suffix))
    return numbers + (0,) * max(0, 8 - len(numbers)), stage, tokens
