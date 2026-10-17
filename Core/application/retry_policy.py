from http.client import HTTPException
from urllib.error import HTTPError, URLError
from ssl import SSLCertVerificationError

from Core.application.contracts import CoreError
from Core.application.settings import CoreConfig


class DownloadRetriesExhausted(CoreError):
    pass


def retry_limit(app):
    config = app.get('config', CoreConfig)
    from Core.application.application_store import ApplicationStore
    try:
        store = app.get('application_store', ApplicationStore)
    except KeyError:
        return config.download_retries
    with store.lock:
        value = store.settings.get('downloadRetries', str(config.download_retries))
    result = int(value)
    if not 0 <= result <= 5:
        from Core.application.diagnostics import diagnostic
        raise ValueError(diagnostic('settings.invalid.retry.limit'))
    return result


def transient_error(error):
    if isinstance(error, (PermissionError, FileNotFoundError, NotADirectoryError, IsADirectoryError, SSLCertVerificationError)):
        return False
    if isinstance(error, HTTPError):
        return error.code in (408, 425, 429) or 500 <= error.code <= 599
    return isinstance(error, (OSError, HTTPException, URLError))
