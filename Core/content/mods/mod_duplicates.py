def file_key(path):
    return path.casefold().removesuffix('.disabled')


def duplicate_kind(destination, version, existing):
    if any(file_key(path) == file_key(destination) for path, number in existing):
        return 'file'
    if version and any(number == version for path, number in existing):
        return 'same'
    return 'duplicate'
