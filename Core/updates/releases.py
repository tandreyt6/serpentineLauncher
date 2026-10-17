from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlsplit, quote
import json
import os
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from Core.application.application_contracts import BackendResult
from Core.application.contracts import CoreEvent, HttpRequest, TaskStage
from Core.application.diagnostics import diagnostic
from Core.application.router import EventManager
from Core.application.tasks import Cancellation, TaskManager
from Core.configuration import settings
from Core.network.network import NetworkManager
from Core.resources.runtime import embedded
from Core.updates.package import EXECUTABLE, MAXIMUM_ARCHIVE, asset_name, extract, version


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class PreparedUpdate:
    version: str
    folder: Path


class UpdateManager:
    def __init__(self, app, config):
        self._app = app
        self._config = config
        self._lock = RLock()
        self.prepared = None
        self.download_task = ''

    @property
    def installable(self):
        return sys.platform == 'win32' and embedded() and Path(sys.executable).name == EXECUTABLE and Path(sys.executable).resolve().parent == self._config.root.resolve()

    def check(self, cancellation):
        network = self._app.get('network', NetworkManager)
        try:
            data = json.loads(network.read(HttpRequest(settings.UPDATE_API_URL), cancellation, 4194304))
        except HTTPError as error:
            if error.code == 404:
                return None
            raise
        if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
            raise ValueError(diagnostic('updates.invalid_release'))
        tag = data.get('tag_name')
        if version(tag) <= version(settings.APP_VERSION):
            return False
        candidates = [item for item in data.get('assets', []) if item.get('name') == asset_name(tag) and item.get('state') == 'uploaded']
        if len(candidates) != 1:
            raise ValueError(diagnostic('updates.missing_asset'))
        item = candidates[0]
        url = item.get('browser_download_url', '')
        parsed = urlsplit(url)
        expected = '/tandreyt6/serpentineLauncher/releases/download/' + quote(tag, safe='') + '/' + asset_name(tag)
        checksum = item.get('digest') or ''
        if parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.path != expected or parsed.query or parsed.fragment or type(item.get('size')) is not int or not 0 < item['size'] <= MAXIMUM_ARCHIVE or not checksum.startswith('sha256:') or len(checksum) != 71 or any(character not in '0123456789abcdef' for character in checksum[7:]):
            raise ValueError(diagnostic('updates.invalid_release'))
        return Release(tag, url, item['size'], checksum[7:])

    def submit(self, release):
        operation = UpdateDownload(self._app, release)
        task = self._app.get('tasks', TaskManager).submit(diagnostic('updates.task_title', release.version), operation.run, stages=(TaskStage('download', .95), TaskStage('verify', .05)), retryable=True)
        self.download_task = task
        self._app.get('events', EventManager).publish(CoreEvent('backend', BackendResult('task.update', release.version, task)))
        return task

    def download(self, release, task, cancellation):
        with self._lock:
            if self.prepared is not None and version(self.prepared.version) >= version(release.version):
                return self.prepared
            tasks = self._app.get('tasks', TaskManager)
            tasks.start_stage(task, 'download')
            folder = Path(tempfile.mkdtemp(prefix='serpentine-update-'))
            archive = folder / 'release.zip'
            checksum, size = sha256(), 0
            began = monotonic()
            try:
                with archive.open('xb') as output, closing(self._app.get('network', NetworkManager).stream(HttpRequest(release.url), cancellation)) as stream:
                    for chunk in stream:
                        cancellation.check()
                        size += len(chunk.data)
                        if size > release.size:
                            raise ValueError(diagnostic('updates.checksum'))
                        checksum.update(chunk.data)
                        output.write(chunk.data)
                        tasks.progress(task, size, release.size, bytes_per_second=size / max(.001, monotonic() - began))
                if size != release.size or checksum.hexdigest() != release.sha256:
                    raise ValueError(diagnostic('updates.checksum'))
                tasks.start_stage(task, 'verify')
                payload = folder / 'payload'
                payload.mkdir()
                extract(archive, payload, release.version, cancellation)
                cancellation.check()
                self.prepared = PreparedUpdate(release.version, folder)
                return self.prepared
            except Exception:
                if folder.resolve().parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith('serpentine-update-'):
                    shutil.rmtree(folder)
                raise

    def arm(self, restart):
        if not self.installable or self.prepared is None:
            raise ValueError(diagnostic('updates.source_mode'))
        folder = self.prepared.folder
        script = folder / 'install.ps1'
        script.write_bytes((settings.ASSETS_DIRECTORY / 'updater.ps1').read_bytes())
        with tempfile.TemporaryFile(dir=self._config.root):
            pass
        plan = folder / ('plan-' + uuid4().hex + '.json')
        plan.write_text(json.dumps(dict(schema=1, pid=os.getpid(), target=str(self._config.root.resolve()), executable=EXECUTABLE, restart=restart, version=self.prepared.version), ensure_ascii=False), encoding='utf-8')
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.Popen([str(shell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', str(script), '-Plan', str(plan)], cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
        return plan

    def disarm(self, plan):
        Path(str(plan) + '.cancel').write_text('cancelled', encoding='ascii')


class UpdateDownload:
    def __init__(self, app, release):
        self._app = app
        self._release = release

    def run(self, task, cancellation):
        return self._app.get('updates', UpdateManager).download(self._release, task, cancellation)
