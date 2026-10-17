from Core.application.diagnostics import diagnostic
import hashlib
import io
import re
import stat
import zipfile
import zlib

from urllib.parse import urlsplit

from Core.application.contracts import Cancelled, CoreError
from Core.content.mods.mod_archive import archive_member_path, checked_zip_directory
from Core.content.mods.mod_parsers import encoded, parse_document
from Core.content.mrpack_contracts import MrpackDependency, MrpackDiagnostic, MrpackFile, MrpackHash, MrpackMetadata, MrpackOverride
from Core.application.settings import CoreConfig
from Core.application.storage import checked_relative
from Core.application.tasks import Cancellation


DEPENDENCY_IDS = frozenset(("minecraft", "forge", "neoforge", "fabric-loader", "quilt-loader"))
ENVIRONMENTS = frozenset(("required", "optional", "unsupported"))
OVERRIDE_SCOPES = {"overrides": "shared", "client-overrides": "client", "server-overrides": "server"}
INDEX_FIELDS = frozenset(("formatVersion", "game", "versionId", "name", "summary", "dependencies", "files"))
FILE_FIELDS = frozenset(("path", "hashes", "downloads", "fileSize", "env"))


def portable_destination(value: object) -> str:
    if not isinstance(value, str) or value.endswith("/"):
        raise CoreError(diagnostic('mrpack_parser.a.relative.portable.file.path.is'))
    archive_member_path(value)
    checked_relative(value)
    return value


def checked_download_url(value: object) -> str:
    if not isinstance(value, str) or not value.isascii() or re.search(r"[^A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]", value) or re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise CoreError(diagnostic('mrpack_parser.download.url.must.be.an.encoded'))
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.fragment or parsed.port not in (None, 443):
        raise CoreError(diagnostic('mrpack_parser.download.url.requires.https.a.host'))
    if any(character in parsed.path + parsed.query for character in "[]"):
        raise CoreError(diagnostic('mrpack_parser.download.url.contains.unencoded.brackets.outside'))
    return value


class MrpackReader:
    def __init__(self, config: CoreConfig, cancellation: Cancellation) -> None:
        self._config = config
        self._cancellation = cancellation
        self._diagnostics: list[MrpackDiagnostic] = []

    def scan(self, data: bytes, relative_path: str) -> MrpackMetadata:
        self._diagnostics = []
        self._cancellation.check()
        if len(data) > self._config.mrpack_archive_bytes:
            raise CoreError(diagnostic('mrpack_parser.mrpack.archive.exceeds.byte.limit'))
        entries = checked_zip_directory(data, self._config.mrpack_archive_entries)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                overrides, others = self._inventory(archive)
                document = self._index(archive)
        except Cancelled:
            raise
        except (zipfile.BadZipFile, UnicodeError, ValueError, RuntimeError, NotImplementedError, OSError, zlib.error) as error:
            raise CoreError(diagnostic('mrpack_parser.cannot.read.mrpack', error)) from error
        if not isinstance(document, dict):
            raise CoreError(diagnostic('mrpack_parser.mrpack.index.must.be.an.object'))
        format_version = document.get("formatVersion")
        if type(format_version) is not int or format_version != 1:
            raise CoreError(diagnostic('mrpack_parser.unsupported.mrpack.formatversion'))
        game = self._required_text(document.get("game"), "game")
        if game != "minecraft":
            raise CoreError(diagnostic('mrpack_parser.unsupported.mrpack.game'))
        version = self._required_text(document.get("versionId"), "versionId")
        name = self._required_text(document.get("name"), "name")
        summary = document.get("summary")
        if summary is not None and not isinstance(summary, str):
            raise CoreError(diagnostic('mrpack_parser.mrpack.summary.must.be.a.string'))
        dependencies = self._dependencies(document.get("dependencies"))
        raw_files = document.get("files")
        if not isinstance(raw_files, list):
            raise CoreError(diagnostic('mrpack_parser.mrpack.files.must.be.an.array'))
        if len(raw_files) > self._config.mrpack_files:
            raise CoreError(diagnostic('mrpack_parser.mrpack.file.count.exceeds.limit'))
        if not raw_files and not overrides:
            self._diagnostic("error", "empty_pack", "files", "Pack contains no indexed files or override files")
        files: list[MrpackFile] = []
        destinations: set[str] = set()
        for position, value in enumerate(raw_files):
            self._cancellation.check()
            source = f"files[{position}]"
            record = self._file(value, source)
            if record is None:
                continue
            folded = record.path.casefold()
            if folded in destinations:
                self._diagnostic("error", "duplicate_destination", source, f"Duplicate MRPACK destination: {record.path}")
                record = MrpackFile(record.path, record.hashes, record.downloads, record.file_size, record.client, record.server, record.environment_declared, False, record.custom_metadata_json, record.raw_metadata_json)
            destinations.add(folded)
            files.append(record)
        self._cancellation.check()
        valid = not any(diagnostic.severity == "error" for diagnostic in self._diagnostics)
        custom = encoded({key: value for key, value in document.items() if key not in INDEX_FIELDS})
        return MrpackMetadata(relative_path, hashlib.sha256(data).hexdigest(), len(data), entries, format_version, game, version, name, summary, dependencies, tuple(files), overrides, others, tuple(self._diagnostics), valid, custom)

    def _diagnostic(self, severity: str, code: str, source: str, message: str) -> None:
        self._diagnostics.append(MrpackDiagnostic(severity, code, source, message))

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise CoreError(diagnostic('mrpack_parser.mrpack.requires.a.nonempty.string', field))
        return value

    def _inventory(self, archive: zipfile.ZipFile) -> tuple[tuple[MrpackOverride, ...], tuple[str, ...]]:
        members: set[str] = set()
        destinations: set[tuple[str, str]] = set()
        overrides: list[MrpackOverride] = []
        others: list[str] = []
        total_bytes = 0
        for info in archive.infolist():
            self._cancellation.check()
            name = archive_member_path(info.filename)
            if info.orig_filename != name or name.casefold() in members:
                raise CoreError(diagnostic('mrpack_parser.duplicate.or.normalized.mrpack.zip.name'))
            members.add(name.casefold())
            mode = (info.external_attr >> 16) & 0xffff
            if info.flag_bits & 1 or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise CoreError(diagnostic('mrpack_parser.encrypted.or.special.mrpack.zip.entry'))
            if info.is_dir():
                if stat.S_IFMT(mode) not in (0, stat.S_IFDIR):
                    raise CoreError(diagnostic('mrpack_parser.mrpack.directory.has.invalid.file.type'))
                continue
            if stat.S_ISDIR(mode):
                raise CoreError(diagnostic('mrpack_parser.mrpack.file.has.directory.type'))
            if info.file_size < 0 or info.compress_size < 0:
                raise CoreError(diagnostic('mrpack_parser.negative.mrpack.zip.sizes'))
            prefix, separator, target = name.partition("/")
            if separator and prefix in OVERRIDE_SCOPES:
                target = portable_destination(target)
                scope = OVERRIDE_SCOPES[prefix]
                key = (scope, target.casefold())
                if key in destinations:
                    raise CoreError(diagnostic('mrpack_parser.duplicate.mrpack.override.destination'))
                destinations.add(key)
                total_bytes += info.file_size
                if info.file_size > self._config.mrpack_override_bytes or total_bytes > self._config.mrpack_overrides_bytes:
                    raise CoreError(diagnostic('mrpack_parser.mrpack.override.sizes.exceed.inventory.limits'))
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    self._diagnostic("error", "unsupported_compression", name, "Override compression is unsupported by the planned importer")
                overrides.append(MrpackOverride(name, target, scope, info.file_size, info.compress_size, info.CRC, info.compress_type))
            elif name != "modrinth.index.json":
                others.append(name)
                self._diagnostic("warning", "unrecognized_entry", name, "Entry is outside recognized override layers")
        return tuple(overrides), tuple(others)

    def _index(self, archive: zipfile.ZipFile) -> object:
        try:
            info = archive.getinfo("modrinth.index.json")
        except KeyError as error:
            raise CoreError(diagnostic('mrpack_parser.root.modrinth.index.json.is.missing')) from error
        limit = self._config.mrpack_index_bytes
        if info.is_dir() or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or info.file_size > limit or info.file_size > max(1, info.compress_size) * self._config.mrpack_compression_ratio:
            raise CoreError(diagnostic('mrpack_parser.mrpack.index.exceeds.limits.or.uses'))
        data = bytearray()
        with archive.open(info) as stream:
            while chunk := stream.read(min(self._config.chunk_bytes, limit + 1 - len(data))):
                self._cancellation.check()
                data.extend(chunk)
                if len(data) > limit:
                    raise CoreError(diagnostic('mrpack_parser.mrpack.index.exceeds.read.limit'))
        if len(data) != info.file_size:
            raise CoreError(diagnostic('mrpack_parser.mrpack.index.size.mismatch'))
        return parse_document(bytes(data), "mrpack-json")

    def _dependencies(self, value: object) -> tuple[MrpackDependency, ...]:
        if not isinstance(value, dict) or not value:
            raise CoreError(diagnostic('mrpack_parser.mrpack.dependencies.requires.a.nonempty.object'))
        result: list[MrpackDependency] = []
        for dependency_id, version in value.items():
            self._required_text(dependency_id, "dependency ID")
            self._required_text(version, f"dependency {dependency_id}")
            known = dependency_id in DEPENDENCY_IDS
            if not known:
                self._diagnostic("warning", "unknown_dependency", f"dependencies.{dependency_id}", "Dependency is preserved but has no supported installer mapping")
            result.append(MrpackDependency(dependency_id, version, known))
        if "minecraft" not in value:
            self._diagnostic("error", "missing_minecraft", "dependencies", "Minecraft version is missing")
        if sum(dependency_id in value for dependency_id in DEPENDENCY_IDS - {"minecraft"}) > 1:
            self._diagnostic("error", "conflicting_loaders", "dependencies", "Multiple loader dependencies require explicit resolution")
        return tuple(result)

    def _file(self, value: object, source: str) -> MrpackFile | None:
        if not isinstance(value, dict):
            self._diagnostic("error", "invalid_file", source, "File entry must be an object")
            return None
        before = len(self._diagnostics)
        raw_path = value.get("path")
        path = raw_path if isinstance(raw_path, str) else ""
        try:
            portable_destination(raw_path)
        except CoreError as error:
            self._diagnostic("error", "unsafe_destination", source, str(error))
        size = value.get("fileSize")
        if type(size) is not int or size < 0 or size > self._config.mrpack_download_file_bytes:
            self._diagnostic("error", "invalid_file_size", source, "fileSize must be a bounded nonnegative integer")
            size = 0
        hashes: list[MrpackHash] = []
        raw_hashes = value.get("hashes")
        if not isinstance(raw_hashes, dict):
            self._diagnostic("error", "invalid_hashes", source, "hashes must be an object")
            raw_hashes = {}
        for algorithm, length in (("sha1", 40), ("sha512", 128)):
            digest = raw_hashes.get(algorithm)
            if not isinstance(digest, str) or not re.fullmatch(f"[0-9a-fA-F]{{{length}}}", digest):
                self._diagnostic("error", "invalid_hash", source, f"Valid {algorithm} is required")
            else:
                hashes.append(MrpackHash(algorithm, digest.lower()))
        for algorithm, digest in raw_hashes.items():
            if algorithm not in ("sha1", "sha512"):
                if isinstance(digest, str):
                    hashes.append(MrpackHash(algorithm, digest))
                else:
                    self._diagnostic("error", "invalid_extra_hash", source, "Additional hash value must be a string")
        raw_downloads = value.get("downloads")
        downloads: list[str] = []
        if not isinstance(raw_downloads, list) or not raw_downloads or len(raw_downloads) > self._config.mrpack_urls_per_file:
            self._diagnostic("error", "invalid_downloads", source, "A bounded nonempty URL array is required")
        else:
            for candidate in raw_downloads:
                if isinstance(candidate, str):
                    downloads.append(candidate)
                try:
                    url = checked_download_url(candidate)
                except (CoreError, ValueError) as error:
                    self._diagnostic("error", "invalid_download_url", source, str(error))
                    continue
                if urlsplit(url).hostname not in self._config.mrpack_allowed_download_hosts:
                    self._diagnostic("warning", "unapproved_download_host", source, "URL host requires separate approval before any download")
        declared = "env" in value
        client = server = "required"
        if declared:
            env = value["env"]
            if not isinstance(env, dict):
                self._diagnostic("error", "invalid_environment", source, "env must be an object")
            else:
                client, server = env.get("client"), env.get("server")
                for side, environment in (("client", client), ("server", server)):
                    if not isinstance(environment, str) or environment not in ENVIRONMENTS:
                        self._diagnostic("error", "invalid_environment", source, f"Unrecognized or missing {side} environment")
                client = client if isinstance(client, str) else None
                server = server if isinstance(server, str) else None
        valid = not any(diagnostic.severity == "error" for diagnostic in self._diagnostics[before:])
        custom = encoded({key: item for key, item in value.items() if key not in FILE_FIELDS})
        return MrpackFile(path, tuple(hashes), tuple(downloads), size, client, server, declared, valid, custom, encoded(value))
