from Core.application.diagnostics import diagnostic
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timezone
from io import BytesIO
import ssl
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPHandler, HTTPSHandler, Request, build_opener, getproxies

from Core.application.contracts import CoreError, HttpChunk, HttpRequest
from Core.application.settings import CoreConfig
from Core.application.tasks import Cancellation
from Core.network.http_pool import HttpConnectionPool
from Core.network.proxy import ConfiguredProxyHandler, proxy_bypass
from Core.configuration.settings import CORE_HTTP_REDIRECT_LIMIT


class SecureRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        current = urlsplit(request.full_url)
        target = urlsplit(new_url)
        if target.scheme not in ("http", "https") or target.username or target.password:
            raise CoreError(diagnostic('network.unsafe.http.redirect'))
        if current.scheme == "https" and target.scheme != "https":
            raise CoreError(diagnostic('network.https.downgrade.rejected'))
        return super().redirect_request(request, response, code, message, headers, new_url)


class RangeUnavailable(CoreError):
    pass


class IncompleteResponse(CoreError):
    pass


class ConnectedHTTPHandler(HTTPHandler):
    def __init__(self, pool, cancellation):
        super().__init__()
        self._pool = pool
        self._cancellation = cancellation

    def http_open(self, request):
        return self.do_open(lambda host, timeout: self._pool.proxy_connection(host, self._cancellation, timeout=timeout), request)


class ConnectedHTTPSHandler(HTTPSHandler):
    def __init__(self, pool, cancellation, context):
        super().__init__(context=context)
        self._pool = pool
        self._cancellation = cancellation

    def https_open(self, request):
        return self.do_open(lambda host, timeout: self._pool.proxy_connection(host, self._cancellation, timeout=timeout, https=True), request)


class NetworkManager:
    def __init__(self, config: CoreConfig) -> None:
        self._config = config
        self._tls_context = ssl.create_default_context()
        self._timeout = min(config.network_timeout, config.network_read_timeout)
        self._pool = HttpConnectionPool(self._tls_context, self._timeout, config.download_workers, min(config.network_timeout, config.network_connect_timeout), config.control_wait_interval, config.network_connect_workers)
        self._proxies = getproxies()

    def _open(self, url, cancellation, offset=0):
        headers = {"User-Agent": self._config.user_agent, "Accept-Encoding": "identity"}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        original = urlsplit(url)
        proxy = self._proxies.get(original.scheme) if not proxy_bypass(original.hostname) else None
        if proxy and urlsplit(proxy).scheme != 'http':
            opened = build_opener(ConfiguredProxyHandler(self._proxies), SecureRedirectHandler(), ConnectedHTTPHandler(self._pool, cancellation), ConnectedHTTPSHandler(self._pool, cancellation, self._tls_context)).open(Request(url, headers=headers), timeout=self._timeout)
            return opened, None, None
        for _ in range(CORE_HTTP_REDIRECT_LIMIT + 1):
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise CoreError(diagnostic('network.unsafe.http.redirect'))
            if original.scheme == 'https' and parsed.scheme != 'https':
                raise CoreError(diagnostic('network.https.downgrade.rejected'))
            cancellation.check()
            proxy = self._proxies.get(parsed.scheme) if not proxy_bypass(parsed.hostname) else None
            try:
                response, key, connection = self._pool.open(url, headers, cancellation, proxy=proxy)
            except ssl.SSLCertVerificationError as error:
                error.add_note(diagnostic('network.certificate_context', parsed.hostname, datetime.now(timezone.utc).isoformat()))
                raise
            if 200 <= response.status < 300:
                return response, key, connection
            location = response.getheader('Location')
            status, reason, response_headers = response.status, response.reason, response.headers
            response.close()
            self._pool.release(key, connection, False)
            if status not in (301, 302, 303, 307, 308) or not location:
                raise HTTPError(url, status, reason, response_headers, BytesIO())
            url = urljoin(url, location)
        raise CoreError(diagnostic('network.redirect.limit'))

    def stream(self, request: HttpRequest, cancellation: Cancellation) -> Iterator[HttpChunk]:
        parsed = urlsplit(request.url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            raise CoreError(diagnostic('network.only.http.s.urls.without.credentials'))
        cancellation.check()
        if type(request.offset) is not int or request.offset < 0:
            raise ValueError(diagnostic('network.invalid.range'))
        try:
            opened, key, connection = self._open(request.url, cancellation, request.offset)
        except HTTPError as error:
            error.close()
            if request.offset and error.code == 416:
                raise RangeUnavailable(diagnostic('network.range.unavailable')) from error
            raise
        reusable = False
        try:
            response = opened
            length_header = response.getheader("Content-Length")
            expected_length = int(length_header) if length_header is not None else None
            if expected_length is not None and expected_length < 0:
                raise CoreError(diagnostic('network.invalid.http.content.length'))
            if request.offset:
                if response.status != 206:
                    raise RangeUnavailable(diagnostic('network.range.unavailable'))
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.getheader('Content-Range', ''))
                if not match:
                    raise CoreError(diagnostic('network.invalid.range'))
                start, end, total = map(int, match.groups())
                if start != request.offset or end < start or end >= total or (expected_length is not None and expected_length != end - start + 1):
                    raise CoreError(diagnostic('network.invalid.range'))
                expected_length = end - start + 1
            elif response.status == 206:
                raise CoreError(diagnostic('network.invalid.range'))
            received = 0
            final_url = urlsplit(response.geturl()) if key is None else parsed
            if final_url.scheme not in ("https", "http"):
                raise CoreError(diagnostic('network.unsafe.redirect.scheme'))
            if parsed.scheme == "https" and final_url.scheme != "https":
                raise CoreError(diagnostic('network.https.downgrade.rejected'))
            while True:
                cancellation.check()
                chunk = response.read1(self._config.chunk_bytes)
                cancellation.check()
                if not chunk:
                    break
                received += len(chunk)
                if expected_length is not None and received > expected_length:
                    raise CoreError(diagnostic('network.http.response.exceeds.content.length'))
                yield HttpChunk(chunk)
            if expected_length is not None and received != expected_length:
                raise IncompleteResponse(diagnostic('network.truncated.http.response'))
            reusable = not response.will_close if key is not None else False
        finally:
            opened.close()
            if connection is not None:
                self._pool.release(key, connection, reusable)

    def read(self, request: HttpRequest, cancellation: Cancellation, maximum_bytes: int) -> bytes:
        chunks: list[bytes] = []
        size = 0
        with closing(self.stream(request, cancellation)) as stream:
            for chunk in stream:
                size += len(chunk.data)
                if size > maximum_bytes:
                    raise CoreError(diagnostic('network.http.response.exceeds.metadata.size.limit'))
                chunks.append(chunk.data)
        return b"".join(chunks)

    def close(self) -> None:
        self._pool.close()
