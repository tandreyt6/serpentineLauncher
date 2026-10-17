import errno
import select
import socket
from threading import RLock
from time import monotonic

from Core.configuration.settings import CORE_NETWORK_ADDRESS_DELAY_SECONDS, CORE_NETWORK_DNS_CACHE_SECONDS
from Core.application.diagnostics import diagnostic


class HttpConnector:
    def __init__(self, timeout, interval):
        self._timeout = timeout
        self._interval = interval
        self._lock = RLock()
        self._addresses = {}
        self._preferred = {}

    def addresses(self, host, port):
        key = host, port
        now = monotonic()
        with self._lock:
            cached = self._addresses.get(key)
            preferred = self._preferred.get(key)
        if cached and cached[0] > now:
            entries = cached[1]
        else:
            entries = tuple(dict.fromkeys(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
            with self._lock:
                self._addresses[key] = monotonic() + CORE_NETWORK_DNS_CACHE_SECONDS, entries
        if not entries:
            raise OSError(diagnostic('network.no.addresses', host))
        first = [entry for entry in entries if entry[0] == entries[0][0]]
        second = [entry for entry in entries if entry[0] != entries[0][0]]
        ordered = []
        while first or second:
            if first:
                ordered.append(first.pop(0))
            if second:
                ordered.append(second.pop(0))
        if preferred:
            ordered.sort(key=lambda entry: entry[4] != preferred)
        return ordered

    def connect(self, address, timeout, source_address, cancellation):
        host, port = address
        entries = self.addresses(host, port)
        cancellation.check_cancelled()
        deadline = monotonic() + min(timeout, self._timeout)
        next_attempt = monotonic()
        pending = {}
        winner = None
        last_error = None
        in_progress = {0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY,
                       getattr(errno, 'WSAEWOULDBLOCK', 10035)}
        try:
            while entries or pending:
                cancellation.check_cancelled()
                now = monotonic()
                if now >= deadline:
                    raise TimeoutError(diagnostic('network.connection.timeout', host))
                if entries and (now >= next_attempt or not pending):
                    family, kind, protocol, _, endpoint = entries.pop(0)
                    try:
                        stream = socket.socket(family, kind, protocol)
                    except OSError as error:
                        last_error = error
                        continue
                    pending[stream] = endpoint
                    try:
                        stream.setblocking(False)
                        if source_address:
                            stream.bind(source_address)
                        status = stream.connect_ex(endpoint)
                        if status == 0:
                            winner = stream
                            break
                        if status not in in_progress:
                            raise OSError(status, diagnostic('network.connection.failed', host, status))
                    except OSError as error:
                        last_error = error
                        pending.pop(stream)
                        stream.close()
                    next_attempt = now + CORE_NETWORK_ADDRESS_DELAY_SECONDS
                if not pending:
                    continue
                delay = min(self._interval, max(0, deadline - monotonic()))
                if entries:
                    delay = min(delay, max(0, next_attempt - monotonic()))
                _, writable, exceptional = select.select([], list(pending), list(pending), delay)
                for stream in dict.fromkeys(writable + exceptional):
                    status = stream.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if status == 0:
                        winner = stream
                        break
                    last_error = OSError(status, diagnostic('network.connection.failed', host, status))
                    pending.pop(stream)
                    stream.close()
                if winner is not None:
                    break
            if winner is None:
                raise last_error or OSError(diagnostic('network.no.addresses', host))
            winner.settimeout(timeout)
            with self._lock:
                self._preferred[host, port] = pending[winner]
            return winner
        finally:
            for stream in pending:
                if stream is not winner:
                    stream.close()
