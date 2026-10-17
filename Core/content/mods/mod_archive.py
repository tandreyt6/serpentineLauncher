from Core.application.diagnostics import diagnostic
import hashlib
import io
import stat
import struct
import zipfile
import zlib

from dataclasses import dataclass
from pathlib import PurePosixPath

from Core.application.contracts import Cancelled, CoreError
from Core.content.mods.mod_contracts import ModDescriptor, ModDiagnostic, ModIconAsset, ModJarMetadata, ModRecord
from Core.content.mods.mod_icons import sanitized_png
from Core.content.mods.mod_parsers import DESCRIPTOR_FORMATS, manifest_values, parse_document, parse_mod_descriptor
from Core.application.settings import CoreConfig
from Core.application.tasks import Cancellation


def archive_member_path(value: str) -> str:
    if not value or "\\" in value or ":" in value or any(ord(char) < 32 for char in value):
        raise CoreError(diagnostic('mod_archive.unsafe.zip.member.path'))
    parts = value.rstrip("/").split("/")
    if PurePosixPath(value).is_absolute() or any(part in ("", ".", "..") for part in parts):
        raise CoreError(diagnostic('mod_archive.unsafe.zip.member.path'))
    return value


def checked_zip_directory(data: bytes, maximum_entries: int) -> int:
    start = max(0, len(data) - 65535 - 22)
    position = data.rfind(b"PK\x05\x06", start)
    while position >= start:
        if position + 22 <= len(data):
            disk, directory_disk, disk_entries, entries, size, offset, comment_size = struct.unpack_from("<HHHHIIH", data, position + 4)
            if position + 22 + comment_size == len(data):
                break
        position = data.rfind(b"PK\x05\x06", start, position)
    if position < start:
        raise CoreError(diagnostic('mod_archive.zip.end.directory.is.missing'))
    if disk or directory_disk or disk_entries != entries or entries == 65535 or size == 0xffffffff or offset == 0xffffffff:
        raise CoreError(diagnostic('mod_archive.split.or.zip.mod.archives.are'))
    if entries > maximum_entries or offset + size != position:
        raise CoreError(diagnostic('mod_archive.zip.directory.exceeds.limits.or.has'))
    cursor = offset
    count = 0
    while cursor < offset + size:
        if cursor + 46 > offset + size or data[cursor:cursor + 4] != b"PK\x01\x02":
            raise CoreError(diagnostic('mod_archive.invalid.zip.central.directory'))
        name_bytes, extra_bytes, comment_bytes = struct.unpack_from("<HHH", data, cursor + 28)
        cursor += 46 + name_bytes + extra_bytes + comment_bytes
        count += 1
        if count > maximum_entries:
            raise CoreError(diagnostic('mod_archive.zip.has.too.many.entries'))
    if cursor != offset + size or count != entries:
        raise CoreError(diagnostic('mod_archive.zip.directory.entry.count.mismatch'))
    return count


@dataclass
class ArchiveBudget:
    read_bytes: int = 0
    entries: int = 0
    records: int = 0


class ModArchiveReader:
    def __init__(self, config: CoreConfig, cancellation: Cancellation) -> None:
        self._config = config
        self._cancellation = cancellation
        self._budget = ArchiveBudget()
        self._descriptors: list[ModDescriptor] = []
        self._mods: list[ModRecord] = []
        self._icons: list[ModIconAsset] = []
        self._diagnostics: list[ModDiagnostic] = []

    def scan(self, data: bytes, relative_path: str, include_nested: bool) -> ModJarMetadata:
        if len(data) > self._config.mod_jar_bytes:
            raise CoreError(diagnostic('mod_archive.mod.jar.exceeds.size.limit'))
        self._visit(data, (), include_nested)
        return ModJarMetadata(relative_path, hashlib.sha256(data).hexdigest(), tuple(self._descriptors), tuple(self._mods), tuple(self._icons), tuple(self._diagnostics))

    def _warning(self, code: str, message: str, source: str, chain: tuple[str, ...]) -> None:
        self._diagnostics.append(ModDiagnostic(code, message, source, chain))

    def _read(self, archive: zipfile.ZipFile, name: str, limit: int) -> bytes:
        self._cancellation.check()
        archive_member_path(name)
        info = archive.getinfo(name)
        if info.file_size > limit or info.file_size > max(1, info.compress_size) * self._config.mod_compression_ratio:
            raise CoreError(diagnostic('mod_archive.zip.entry.exceeds.size.or.compression'))
        if self._budget.read_bytes + info.file_size > self._config.mod_scan_bytes:
            raise CoreError(diagnostic('mod_archive.mod.scan.exceeds.total.decompression.budget'))
        result = bytearray()
        with archive.open(info) as stream:
            while chunk := stream.read(min(self._config.chunk_bytes, limit + 1 - len(result))):
                self._cancellation.check()
                result.extend(chunk)
                self._budget.read_bytes += len(chunk)
                if len(result) > limit or self._budget.read_bytes > self._config.mod_scan_bytes:
                    raise CoreError(diagnostic('mod_archive.zip.entry.exceeds.read.budget'))
        if len(result) != info.file_size:
            raise CoreError(diagnostic('mod_archive.zip.entry.size.mismatch'))
        return bytes(result)

    def _visit(self, data: bytes, chain: tuple[str, ...], include_nested: bool) -> None:
        self._cancellation.check()
        entries = checked_zip_directory(data, self._config.mod_archive_entries)
        self._budget.entries += entries
        if self._budget.entries > self._config.mod_scan_entries:
            raise CoreError(diagnostic('mod_archive.mod.scan.exceeds.total.zip.entry'))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set()
            for member in archive.infolist():
                archive_member_path(member.filename)
                if member.filename != member.orig_filename or member.filename in names or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                    raise CoreError(diagnostic('mod_archive.duplicate.symbolic.link.or.encrypted.zip'))
                names.add(member.filename)
            manifest = ()
            if "META-INF/MANIFEST.MF" in names:
                try:
                    manifest = manifest_values(self._read(archive, "META-INF/MANIFEST.MF", self._config.mod_metadata_bytes))
                except Cancelled:
                    raise
                except (CoreError, zipfile.BadZipFile, RuntimeError) as error:
                    self._warning("manifest_error", str(error), "META-INF/MANIFEST.MF", chain)
            nested = []
            found = False
            for source in DESCRIPTOR_FORMATS:
                if source not in names:
                    continue
                found = True
                try:
                    parsed = parse_mod_descriptor(self._read(archive, source, self._config.mod_metadata_bytes), source, chain, manifest)
                    self._budget.records += len(parsed.mods)
                    if self._budget.records > self._config.mod_records:
                        raise CoreError(diagnostic('mod_archive.mod.record.count.exceeds.limit'))
                    self._descriptors.append(parsed.descriptor)
                    self._mods.extend(parsed.mods)
                    self._diagnostics.extend(parsed.diagnostics)
                    nested.extend(parsed.nested_paths)
                    self._read_icons(archive, parsed.mods, chain)
                except Cancelled:
                    raise
                except (CoreError, ValueError, TypeError, KeyError, RecursionError, zipfile.BadZipFile, RuntimeError) as error:
                    loaders = {"fabric_json": ("Fabric",), "quilt_json": ("Quilt",), "neoforge_toml": ("NeoForge",), "forge_legacy_json": ("Forge",), "forge_toml": ("Forge", "NeoForge")}[DESCRIPTOR_FORMATS[source]]
                    self._descriptors.append(ModDescriptor(source, DESCRIPTOR_FORMATS[source], loaders, chain, (), parse_status="invalid"))
                    self._warning("descriptor_error", str(error), source, chain)
            if not found:
                self._warning("unknown_jar", "No recognized mod descriptor; this may be a library or unsupported mod", "", chain)
            if "quilt.mod.json5" in names:
                self._warning("development_metadata", "quilt.mod.json5 is a development artifact, not production metadata", "quilt.mod.json5", chain)
            if "META-INF/jarjar/metadata.json" in names:
                try:
                    jarjar = parse_document(self._read(archive, "META-INF/jarjar/metadata.json", self._config.mod_metadata_bytes), "jarjar_json")
                    if not isinstance(jarjar, dict) or not isinstance(jarjar.get("jars"), list):
                        raise CoreError(diagnostic('mod_archive.invalid.jarjar.metadata'))
                    nested.extend(entry["path"] for entry in jarjar["jars"] if isinstance(entry, dict) and isinstance(entry.get("path"), str))
                except Cancelled:
                    raise
                except (CoreError, ValueError, RecursionError, zipfile.BadZipFile, RuntimeError) as error:
                    self._warning("nested_metadata_error", str(error), "META-INF/jarjar/metadata.json", chain)
            if not include_nested:
                return
            for path in dict.fromkeys(nested):
                try:
                    if len(chain) >= self._config.mod_nested_depth:
                        raise CoreError(diagnostic('mod_archive.nested.jar.depth.limit.reached'))
                    nested_data = self._read(archive, path, self._config.mod_nested_jar_bytes)
                    self._visit(nested_data, (*chain, path), include_nested)
                except Cancelled:
                    raise
                except (CoreError, ValueError, KeyError, RecursionError, zipfile.BadZipFile, RuntimeError) as error:
                    self._warning("nested_jar_error", str(error), path, chain)

    def _read_icons(self, archive: zipfile.ZipFile, records: tuple[ModRecord, ...], chain: tuple[str, ...]) -> None:
        paths = dict.fromkeys(reference.member_path for record in records for reference in record.icons)
        existing = {icon.member_path for icon in self._icons if icon.archive_chain == chain}
        for path in paths:
            if path in existing:
                continue
            try:
                raw = self._read(archive, path, self._config.mod_icon_bytes)
                width, height, png = sanitized_png(raw, self._config)
                self._icons.append(ModIconAsset(path, chain, width, height, hashlib.sha256(png).hexdigest(), png))
                if any(reference.declared_size is not None and (width != reference.declared_size or height != reference.declared_size) for record in records for reference in record.icons if reference.member_path == path):
                    self._warning("icon_size_mismatch", "PNG dimensions differ from the declared icon size", path, chain)
            except Cancelled:
                raise
            except (CoreError, ValueError, KeyError, zipfile.BadZipFile, RuntimeError, zlib.error) as error:
                self._warning("icon_error", str(error), path, chain)
