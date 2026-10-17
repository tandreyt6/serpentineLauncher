from argparse import ArgumentParser
from dataclasses import replace
import json
from pathlib import Path
import ssl
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.parse import urlsplit


def run(arguments):
    parser = ArgumentParser()
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--direct', action='store_true')
    options = parser.parse_args(arguments)
    began = monotonic()
    records = []

    def record(event, **values):
        row = {'event': event, 'elapsed_seconds': round(monotonic() - began, 3), **values}
        records.append(row)
        if options.output:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        sys.stdout.write(json.dumps(row, ensure_ascii=False) + '\n')
        sys.stdout.flush()

    record('starting', python=sys.version.split()[0], openssl=ssl.OPENSSL_VERSION)
    from Core.application.bootstrap import create_core_config
    from Core.content.catalogue import CatalogueManager
    from Core.network.network import NetworkManager
    from Core.application.runtime import CoreRuntime
    from Core.application.tasks import Cancellation
    with TemporaryDirectory(prefix='serpentine-network-', dir=options.directory) as temporary:
        core = CoreRuntime(replace(create_core_config(), root=Path(temporary)))
        network = core.app.get('network', NetworkManager)
        if options.direct:
            network._proxies = {}
        proxies = {scheme: {'host': urlsplit(value).hostname, 'port': urlsplit(value).port} for scheme, value in network._proxies.items() if scheme in ('http', 'https')}
        record('initialized', proxies=proxies, verify_hostname=network._tls_context.check_hostname, certificate_validation=network._tls_context.verify_mode)
        pool_open = network._pool.open

        def open_request(url, *values, **settings):
            parsed = urlsplit(url)
            record('request.start', host=parsed.hostname, path=parsed.path, proxy=bool(settings.get('proxy')))
            started = monotonic()
            try:
                response, key, connection = pool_open(url, *values, **settings)
                record('request.headers', host=parsed.hostname, seconds=round(monotonic()-started, 3), status=response.status)
                return response, key, connection
            except Exception as error:
                record('request.failed', host=parsed.hostname, seconds=round(monotonic()-started, 3), error_type=type(error).__name__)
                raise

        network._pool.open = open_request
        try:
            catalogue = core.app.get('catalogue', CatalogueManager)
            for loader in ('Vanilla', 'Fabric', 'Forge', 'NeoForge', 'Quilt'):
                record('catalogue.start', loader=loader)
                started = monotonic()
                try:
                    source = catalogue.fetch_source(loader, Cancellation())
                    record('catalogue.complete', loader=loader, seconds=round(monotonic()-started, 3), games=len(source.games), versions=len(source.versions), cores=len(source.cores))
                except Exception as error:
                    record('catalogue.failed', loader=loader, seconds=round(monotonic()-started, 3), error_type=type(error).__name__)
        finally:
            core.close()
    record('complete')
    return 1 if any(row['event'] in ('catalogue.failed', 'request.failed') for row in records) else 0
