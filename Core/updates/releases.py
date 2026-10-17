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
import re
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
from Core.updates.version import UPDATER_EXECUTABLE, updater_asset_name


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    size: int
    sha256: str
    updater: object = None


@dataclass(frozen=True)
class PreparedUpdate:
    version: str
    folder: Path
    sha256: str = ''
    updater: Path | None = None


class UpdateManager:
    def __init__(self, app, config):
        self._app = app
        self._config = config
        self._lock = RLock()
        self.prepared = None
        self.download_task = ''
        self._process = None
        self._plan = None
        self._abort_event = None
        self._ready_event = None
        self._system_ending = False

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
        updater = None
        binaries = [entry for entry in data.get('assets', []) if re.fullmatch(r'serpentineUpdater-[0-9]+\.[0-9]+\.[0-9]+-windows-x64\.exe', entry.get('name', '')) and entry.get('state') == 'uploaded']
        if len(binaries) > 1:
            raise ValueError(diagnostic('updates.invalid_release'))
        if binaries:
            binary = binaries[0]
            binary_version = binary['name'].removeprefix('serpentineUpdater-').removesuffix('-windows-x64.exe')
            version(binary_version)
            parsed = urlsplit(binary.get('browser_download_url', ''))
            expected = '/tandreyt6/serpentineLauncher/releases/download/' + quote(tag, safe='') + '/' + updater_asset_name(binary_version)
            checksum = binary.get('digest') or ''
            if parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.path != expected or parsed.query or parsed.fragment or type(binary.get('size')) is not int or not 0 < binary['size'] <= 16777216 or not re.fullmatch(r'sha256:[0-9a-f]{64}', checksum):
                raise ValueError(diagnostic('updates.invalid_release'))
            updater = Release(binary_version, binary['browser_download_url'], binary['size'], checksum[7:])
        return Release(tag, url, item['size'], item['digest'][7:], updater)

    def submit(self, release):
        operation = UpdateDownload(self._app, release)
        stages = ((TaskStage('updater', .1), TaskStage('download', .85), TaskStage('verify', .05)) if release.updater else (TaskStage('download', .95), TaskStage('verify', .05)))
        task = self._app.get('tasks', TaskManager).submit(diagnostic('updates.task_title', release.version), operation.run, stages=stages, retryable=True)
        self.download_task = task
        self._app.get('events', EventManager).publish(CoreEvent('backend', BackendResult('task.update', release.version, task)))
        return task

    def download(self, release, task, cancellation):
        with self._lock:
            if self.prepared is not None and version(self.prepared.version) >= version(release.version):
                return self.prepared
            tasks = self._app.get('tasks', TaskManager)
            folder = Path(tempfile.mkdtemp(prefix='serpentine-update-'))
            archive = folder / 'release.zip'
            checksum, size = sha256(), 0
            began = monotonic()
            try:
                updater_path = self._download_updater(release.updater, folder, tasks, task, cancellation) if release.updater else None
                tasks.start_stage(task, 'download')
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
                if release.updater is not None:
                    from Core.updates.package import digest
                    if digest(payload / UPDATER_EXECUTABLE) != release.updater.sha256:
                        raise ValueError(diagnostic('updates.checksum'))
                cancellation.check()
                self.prepared = PreparedUpdate(release.version, folder, release.sha256, updater_path)
                return self.prepared
            except Exception:
                if folder.resolve().parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith('serpentine-update-'):
                    shutil.rmtree(folder)
                raise

    def _download_updater(self, release, folder, tasks, task, cancellation):
        tasks.start_stage(task, 'updater')
        installed = self._config.root / UPDATER_EXECUTABLE
        if os.name == 'nt':
            from Core.updates.windows import file_version
            if installed.is_file() and file_version(installed) >= version(release.version):
                tasks.progress(task, release.size, release.size)
                return installed
        path = folder / UPDATER_EXECUTABLE
        checksum, size = sha256(), 0
        with path.open('xb') as output, closing(self._app.get('network', NetworkManager).stream(HttpRequest(release.url), cancellation)) as stream:
            for chunk in stream:
                cancellation.check()
                size += len(chunk.data)
                if size > release.size:
                    raise ValueError(diagnostic('updates.checksum'))
                checksum.update(chunk.data)
                output.write(chunk.data)
                tasks.progress(task, size, release.size)
        if size != release.size or checksum.hexdigest() != release.sha256:
            raise ValueError(diagnostic('updates.checksum'))
        if os.name == 'nt' and file_version(path) != version(release.version):
            raise ValueError(diagnostic('updates.invalid_release'))
        return path

    def arm(self, restart):
        if not self.installable or self.prepared is None:
            raise ValueError(diagnostic('updates.source_mode'))
        with self._lock:
            if self._system_ending:
                raise ValueError(diagnostic('updates.cancelled'))
            if self.armed:
                return self._plan
            from Core.updates.windows import WindowsEvent
            for event in (self._abort_event, self._ready_event):
                if event is not None:
                    event.close()
            identity = uuid4().hex
            self._abort_event = WindowsEvent('Local\\SerpentineUpdateAbort-' + identity)
            self._ready_event = WindowsEvent('Local\\SerpentineUpdateReady-' + identity)
            if self._system_ending:
                self._abort_event.set()
                raise ValueError(diagnostic('updates.cancelled'))
            folder = self.prepared.folder / ('runner-' + identity)
            folder.mkdir()
            runner = folder / UPDATER_EXECUTABLE
            shutil.copy2(self.prepared.updater or self._config.root / runner.name, runner)
            archive = self.prepared.folder / 'release.zip'
            with tempfile.TemporaryFile(dir=self._config.root):
                pass
            plan = folder / 'plan.json'
            plan.write_text(json.dumps(dict(schema=2, pid=os.getpid(), target=str(self._config.root.resolve()), executable=EXECUTABLE,
                archive=str(archive.resolve()), size=archive.stat().st_size, sha256=self.prepared.sha256 or self._archive_digest(archive),
                version=self.prepared.version, abortEvent=self._abort_event.name, readyEvent=self._ready_event.name), ensure_ascii=False), encoding='utf-8')
            self._process = subprocess.Popen([str(runner), '--plan', str(plan)], cwd=folder, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
            self._plan = plan
            deadline = monotonic() + 5
            while not self._ready_event.wait(25):
                if self._system_ending or self._process.poll() is not None or monotonic() >= deadline:
                    self.disarm(plan)
                    raise ValueError(diagnostic('updates.updater_start'))
            return plan

    @staticmethod
    def _archive_digest(archive):
        from Core.updates.package import digest
        return digest(archive)

    @property
    def armed(self):
        return self._process is not None and self._process.poll() is None and self._abort_event is not None and not self._abort_event.wait(0)

    def commit(self, plan, restart):
        if self._system_ending or not self.armed or Path(plan) != self._plan:
            raise ValueError(diagnostic('updates.cancelled'))
        path = Path(str(plan) + '.commit')
        temporary = path.with_suffix('.pending')
        temporary.write_text(json.dumps(dict(restart=bool(restart))), encoding='utf-8')
        temporary.replace(path)

    def abort(self):
        self._system_ending = True
        if self._abort_event is not None:
            self._abort_event.set()

    def resume(self):
        self._system_ending = False

    def disarm(self, plan):
        if self._plan == plan and self._abort_event is not None:
            self._abort_event.set()
        else:
            Path(str(plan) + '.cancel').write_text('cancelled', encoding='ascii')


class UpdateDownload:
    def __init__(self, app, release):
        self._app = app
        self._release = release

    def run(self, task, cancellation):
        return self._app.get('updates', UpdateManager).download(self._release, task, cancellation)
