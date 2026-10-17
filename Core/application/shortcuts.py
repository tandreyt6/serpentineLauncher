from Core.configuration.settings import SHORTCUT_ACTIONS, SHORTCUT_RESERVED


def identity(sequence):
    value = sequence.casefold()
    return value[:-5] + 'return' if value.endswith('enter') else value


def conflicts(settings, action, sequence):
    scopes = next((set(scopes) for key, default, scopes in SHORTCUT_ACTIONS if key == action), set())
    return [key for key, default, other_scopes in SHORTCUT_ACTIONS
            if key != action and sequence and scopes.intersection(other_scopes)
            and identity(settings['shortcut.' + key]) == identity(sequence)]


def setting_valid(settings, key, sequence):
    action = key.removeprefix('shortcut.')
    return (action in {entry[0] for entry in SHORTCUT_ACTIONS} and isinstance(sequence, str)
            and len(sequence) <= 64 and '\n' not in sequence and '\r' not in sequence
            and sequence.casefold() not in {value.casefold() for value in SHORTCUT_RESERVED}
            and not conflicts(settings, action, sequence))
