from collections import defaultdict
from base64 import b64encode
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from threading import BoundedSemaphore, RLock
from urllib.parse import unquote, urlsplit

from Core.application.diagnostics import diagnostic
from Core.application.contracts import CoreError
from Core.network.http_connector import HttpConnector
from Core.configuration.settings import CORE_CONTROL_WAIT_INTERVAL_SECONDS, CORE_NETWORK_CONNECT_WORKERS


class HttpConnectionPool:
    def __init__(self, tls_context, timeout, idle_limit, connect_timeout=None, interval=CORE_CONTROL_WAIT_INTERVAL_SECONDS, connect_workers=CORE_NETWORK_CONNECT_WORKERS):
        self._tls = tls_context
        self._timeout = timeout
        self._limit = idle_limit
        self._idle = defaultdict(list)
        self._lock = RLock()
        self._closed = False
        self._connector = HttpConnector(connect_timeout or timeout, interval)
        self._connect_slots = BoundedSemaphore(connect_workers)
        self._interval = interval

    def _configure(self, connection, cancellation):
        connection._create_connection = lambda address, timeout, source_address: self._connector.connect(address, timeout, source_address, cancellation)
        if not hasattr(connection, '_launcher_connect'):
            connection._launcher_connect = connection.connect

        def connect():
            cancellation.check()
            while not self._connect_slots.acquire(timeout=self._interval):
                cancellation.check()
            try:
                cancellation.check_cancelled()
                return connection._launcher_connect()
            finally:
                self._connect_slots.release()

        connection.connect = connect
        return connection

    def _create(self, key, cancellation):
        scheme, host, port, proxy = key
        endpoint = urlsplit(proxy) if proxy else None
        connect_host, connect_port = (endpoint.hostname, endpoint.port or 80) if endpoint else (host, port)
        if scheme == 'https':
            connection = HTTPSConnection(connect_host, connect_port, timeout=self._timeout, context=self._tls)
            if endpoint:
                connection.set_tunnel(host, port or 443, headers=self._proxy_headers(endpoint))
        else:
            connection = HTTPConnection(connect_host, connect_port, timeout=self._timeout)
        return self._configure(connection, cancellation)

    @staticmethod
    def _proxy_headers(endpoint):
        if endpoint.username is None:
            return {}
        credentials = unquote(endpoint.username) + ':' + unquote(endpoint.password or '')
        return {'Proxy-Authorization': 'Basic ' + b64encode(credentials.encode()).decode('ascii')}

    def proxy_connection(self, host, cancellation, *, timeout, https=False):
        connection = HTTPSConnection(host, timeout=timeout, context=self._tls) if https else HTTPConnection(host, timeout=timeout)
        return self._configure(connection, cancellation)

    def open(self, url, headers, cancellation, proxy=None):
        parsed = urlsplit(url)
        key = parsed.scheme, parsed.hostname, parsed.port, proxy
        with self._lock:
            if self._closed:
                raise CoreError(diagnostic('network.pool.closed'))
            available = self._idle[key]
            reused = bool(available)
            connection = available.pop() if reused else self._create(key, cancellation)
        self._configure(connection, cancellation)
        target = parsed.path or '/'
        if parsed.query:
            target += '?' + parsed.query
        if proxy and parsed.scheme == 'http':
            target = url
            headers = dict(headers, **self._proxy_headers(urlsplit(proxy)))
        try:
            cancellation.check()
            try:
                connection.request('GET', target, headers=headers)
                response = connection.getresponse()
            except (OSError, HTTPException):
                if not reused:
                    raise
                connection.close()
                cancellation.check()
                connection = self._create(key, cancellation)
                connection.request('GET', target, headers=headers)
                response = connection.getresponse()
            return response, key, connection
        except BaseException:
            connection.close()
            raise

    def release(self, key, connection, reusable):
        with self._lock:
            if reusable and not self._closed and len(self._idle[key]) < self._limit:
                self._idle[key].append(connection)
                return
        connection.close()

    def close(self):
        with self._lock:
            self._closed = True
            connections = [connection for entries in self._idle.values() for connection in entries]
            self._idle.clear()
        for connection in connections:
            connection.close()
