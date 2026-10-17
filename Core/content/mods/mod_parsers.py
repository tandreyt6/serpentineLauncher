from Core.application.diagnostics import diagnostic
import hashlib
import json
import re
import tomllib

from dataclasses import replace
from datetime import date, datetime, time

from Core.application.contracts import CoreError
from Core.content.mods.mod_contracts import ModDependency, ModDescriptor, ModDiagnostic, ModIconReference, ModLicense, ModPerson, ModRecord, ParsedModDescriptor


DESCRIPTOR_FORMATS = {
    "fabric.mod.json": "fabric_json",
    "quilt.mod.json": "quilt_json",
    "META-INF/mods.toml": "forge_toml",
    "META-INF/neoforge.mods.toml": "neoforge_toml",
    "mcmod.info": "forge_legacy_json",
}


def object_map(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise CoreError(diagnostic('mod_parsers.metadata.object.expected'))
    return value


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise CoreError(diagnostic('mod_parsers.metadata.array.expected'))
    return value


def text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=encoded_special)


def encoded_special(value: object) -> str:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    raise TypeError(diagnostic('mod_parsers.unsupported.metadata.value'))


def string_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        return ()
    return tuple((key, item) for key, item in value.items() if isinstance(key, str) and isinstance(item, str))


def string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(item for item in value if isinstance(item, str)) if isinstance(value, list) else ()


def people(value: object, role: str) -> tuple[ModPerson, ...]:
    result = []
    for entry in value if isinstance(value, list) else ():
        if isinstance(entry, str):
            result.append(ModPerson(entry, (role,)))
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
            result.append(ModPerson(entry["name"], (role,), string_pairs(entry.get("contact", {}))))
    return tuple(result)


def licenses(value: object) -> tuple[ModLicense, ...]:
    entries = value if isinstance(value, list) else [value]
    result = []
    for entry in entries:
        if isinstance(entry, str):
            result.append(ModLicense(entry))
        elif isinstance(entry, dict):
            result.append(ModLicense(text(entry.get("id")), text(entry.get("name")), text(entry.get("url")), text(entry.get("description"))))
    return tuple(result)


def icon_references(value: object) -> tuple[ModIconReference, ...]:
    if isinstance(value, str) and value:
        return (ModIconReference(value),)
    result = []
    for key, path in value.items() if isinstance(value, dict) else ():
        if isinstance(key, str) and key.isascii() and key.isdecimal() and 0 < int(key) and isinstance(path, str):
            result.append(ModIconReference(path, int(key)))
    return tuple(result)


def manifest_values(data: bytes) -> tuple[tuple[str, str], ...]:
    lines = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded = []
    for line in lines:
        if not line:
            break
        if line.startswith(" ") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return tuple((key.lower(), value) for line in unfolded if ": " in line for key, value in [line.split(": ", 1)])


def substituted_version(raw: str, properties: dict[str, object], manifest: tuple[tuple[str, str], ...]) -> str:
    values = {f"file.{key}": value for key, value in properties.items() if isinstance(value, str)}
    values["file.jarVersion"] = dict(manifest).get("implementation-version", "")
    seen = set()
    value = raw
    while "${" in value:
        if value in seen:
            return ""
        seen.add(value)
        matches = tuple(re.finditer(r"\$\{([^{}]+)\}", value))
        if not matches or any(match.group(1) not in values or not values[match.group(1)] for match in matches):
            return ""
        replacements = [values[match.group(1)] for match in matches]
        if any("${" in replacement for replacement in replacements):
            return ""
        for match in reversed(matches):
            value = value[:match.start()] + values[match.group(1)] + value[match.end():]
    return value


def reject_json_constant(value: str) -> object:
    raise CoreError(diagnostic('mod_parsers.invalid.json.constant', value))


def unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise CoreError(diagnostic('mod_parsers.duplicate.metadata.key', key))
        value[key] = item
    return value


def parse_document(data: bytes, metadata_format: str) -> object:
    value = data.decode("utf-8-sig")
    if metadata_format.endswith("toml"):
        return tomllib.loads(value)
    return json.loads(value, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)


def base_record(value: dict[str, object], source: str, chain: tuple[str, ...], index: int, loaders: tuple[str, ...], metadata_format: str, mod_id_key: str, name_key: str) -> ModRecord:
    mod_id = text(value.get(mod_id_key))
    key = hashlib.sha256(encoded((chain, source, index, mod_id)).encode("utf-8")).hexdigest()
    raw_version = text(value.get("version"))
    version = "" if "${" in raw_version else raw_version
    return ModRecord(key, mod_id, text(value.get(name_key), mod_id) or mod_id, version, raw_version, text(value.get("description")), loaders, metadata_format, source, chain, custom_metadata_json=encoded(value))


def fabric_dependencies(value: dict[str, object], schema: int) -> tuple[ModDependency, ...]:
    result = []
    keys = ("depends", "recommends", "suggests", "conflicts", "breaks") if schema == 1 else ("requires", "recommends", "conflicts")
    for key in keys:
        for mod_id, ranges in value.get(key, {}).items() if isinstance(value.get(key), dict) else ():
            expression = ranges if isinstance(ranges, str) else encoded(ranges)
            result.append(ModDependency(mod_id, key, expression, "fabric", raw_expression=encoded(ranges)))
    return tuple(result)


def parse_fabric(value: object, source: str, chain: tuple[str, ...]) -> ParsedModDescriptor:
    data = object_map(value)
    schema = data.get("schemaVersion", 0)
    if isinstance(schema, bool) or not isinstance(schema, int) or schema not in (0, 1):
        raise CoreError(diagnostic('mod_parsers.unsupported.fabric.metadata.schema'))
    record = base_record(data, source, chain, 0, ("Fabric",), "fabric_json", "id", "name")
    contact = data.get("contact", {}) if schema == 1 else data.get("links", {})
    if isinstance(contact, str):
        contact = {"homepage": contact}
    record = replace(record, authors=people(data.get("authors", []), "author"), contributors=people(data.get("contributors", []), "contributor"), licenses=licenses(data.get("license", [])), contacts=string_pairs(contact), dependencies=fabric_dependencies(data, schema), icons=icon_references(data.get("icon")), environment=text(data.get("environment"), "*") or "*", provided_ids=string_values(data.get("provides", [])))
    nested = tuple(text(entry.get("file")) for entry in data.get("jars", []) if isinstance(entry, dict)) if isinstance(data.get("jars", []), list) else ()
    return ParsedModDescriptor(ModDescriptor(source, "fabric_json", ("Fabric",), chain, (record.record_key,), schema), (record,), nested, ())


def quilt_dependencies(value: dict[str, object]) -> tuple[ModDependency, ...]:
    result = []
    for kind in ("depends", "breaks"):
        entries = value.get(kind, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, str):
                result.append(ModDependency(entry, kind, "*", "quilt", raw_expression=encoded(entry)))
            elif isinstance(entry, dict):
                ranges = entry.get("versions", "*")
                expression = ranges if isinstance(ranges, str) else encoded(ranges)
                result.append(ModDependency(text(entry.get("id")), "optional" if entry.get("optional") is True and kind == "depends" else kind, expression, "quilt", text(entry.get("environment")), reason=text(entry.get("reason")), raw_expression=encoded(entry)))
            elif isinstance(entry, list):
                result.append(ModDependency("", kind, encoded(entry), "quilt", raw_expression=encoded(entry)))
    return tuple(result)


def parse_quilt(value: object, source: str, chain: tuple[str, ...]) -> ParsedModDescriptor:
    data = object_map(value)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CoreError(diagnostic('mod_parsers.unsupported.quilt.metadata.schema'))
    loader = object_map(data.get("quilt_loader"))
    metadata = object_map(loader.get("metadata", {}))
    record = base_record(loader, source, chain, 0, ("Quilt",), "quilt_json", "id", "name")
    contributors = tuple(ModPerson(name, string_values(roles)) for name, roles in metadata.get("contributors", {}).items()) if isinstance(metadata.get("contributors"), dict) else ()
    environment = text(data.get("minecraft", {}).get("environment"), "*") if isinstance(data.get("minecraft", {}), dict) else "unknown"
    provided = tuple(text(entry.get("id")) if isinstance(entry, dict) else text(entry) for entry in loader.get("provides", [])) if isinstance(loader.get("provides", []), list) else ()
    record = replace(record, name=text(metadata.get("name"), record.mod_id) or record.mod_id, description=text(metadata.get("description")), contributors=contributors, licenses=licenses(metadata.get("license", [])), contacts=string_pairs(metadata.get("contact", {})), dependencies=quilt_dependencies(loader), icons=icon_references(metadata.get("icon")), environment=environment, provided_ids=provided, custom_metadata_json=encoded(data))
    return ParsedModDescriptor(ModDescriptor(source, "quilt_json", ("Quilt",), chain, (record.record_key,), 1), (record,), string_values(loader.get("jars", [])), ())


def toml_loaders(source: str, dependencies: tuple[ModDependency, ...]) -> tuple[str, ...]:
    if source == "META-INF/neoforge.mods.toml":
        return ("NeoForge",)
    ids = {entry.mod_id for entry in dependencies}
    if "neoforge" in ids:
        return ("Forge", "NeoForge") if "forge" in ids else ("NeoForge",)
    return ("Forge",) if "forge" in ids else ("Forge", "NeoForge")


def parse_toml(value: object, source: str, chain: tuple[str, ...], manifest: tuple[tuple[str, str], ...]) -> ParsedModDescriptor:
    data = object_map(value)
    metadata_format = DESCRIPTOR_FORMATS[source]
    records = []
    for index, entry in enumerate(sequence(data.get("mods", []))):
        mod = object_map(entry)
        mod_id = text(mod.get("modId"))
        dependencies = []
        dependency_map = data.get("dependencies", {})
        entries = dependency_map.get(mod_id, []) if isinstance(dependency_map, dict) else []
        for dependency in entries if isinstance(entries, list) else ():
            if not isinstance(dependency, dict):
                continue
            kind = text(dependency.get("type")) or ("required" if dependency.get("mandatory", True) is True else "optional")
            dependencies.append(ModDependency(text(dependency.get("modId")), kind, text(dependency.get("versionRange")), "maven", text(dependency.get("side"), "BOTH"), text(dependency.get("ordering"), "NONE"), text(dependency.get("reason")), encoded(dependency)))
        record = base_record(mod, source, chain, index, toml_loaders(source, tuple(dependencies)), metadata_format, "modId", "displayName")
        properties = data.get("properties", {}) if isinstance(data.get("properties", {}), dict) else {}
        contacts = tuple((key, text(owner.get(key))) for key, owner in (("displayURL", mod), ("updateJSONURL", mod), ("issueTrackerURL", data), ("modUrl", mod)) if isinstance(owner.get(key), str))
        record = replace(record, version=substituted_version(record.raw_version, properties, manifest), authors_text=text(mod.get("authors")), licenses=licenses(data.get("license", [])), contacts=contacts, dependencies=tuple(dependencies), icons=icon_references(mod.get("logoFile", data.get("logoFile"))), environment="client" if data.get("clientSideOnly") is True else "unknown", language_loader=text(data.get("modLoader")), language_loader_range=text(data.get("loaderVersion")), credits=text(mod.get("credits")))
        records.append(record)
    loaders = tuple(sorted({loader for record in records for loader in record.loaders}))
    return ParsedModDescriptor(ModDescriptor(source, metadata_format, loaders, chain, tuple(record.record_key for record in records), custom_metadata_json=encoded(data)), tuple(records), (), ())


def parse_legacy(value: object, source: str, chain: tuple[str, ...]) -> ParsedModDescriptor:
    entries = value if isinstance(value, list) else object_map(value).get("modList", [])
    records = []
    for index, entry in enumerate(sequence(entries)):
        mod = object_map(entry)
        record = base_record(mod, source, chain, index, ("Forge",), "forge_legacy_json", "modid", "name")
        dependencies = tuple(ModDependency(mod_id, kind, "", "legacy") for kind in ("requiredMods", "dependencies", "dependants") for mod_id in string_values(mod.get(kind, [])))
        if text(mod.get("mcversion")):
            dependencies += (ModDependency("minecraft", "declared_mcversion", text(mod["mcversion"]), "legacy"),)
        contacts = tuple((key, mod[key]) for key in ("url", "updateJSON", "updateUrl") if isinstance(mod.get(key), str))
        record = replace(record, authors=people(mod.get("authorList", []), "author"), contacts=contacts, dependencies=dependencies, icons=icon_references(mod.get("logoFile")), credits=text(mod.get("credits")))
        records.append(record)
    warning = ModDiagnostic("legacy_runtime_metadata", "mcmod.info does not prove runtime @Mod values or compatibility", source, chain)
    return ParsedModDescriptor(ModDescriptor(source, "forge_legacy_json", ("Forge",), chain, tuple(record.record_key for record in records)), tuple(records), (), (warning,))


def parse_mod_descriptor(data: bytes, source: str, chain: tuple[str, ...] = (), manifest: tuple[tuple[str, str], ...] = ()) -> ParsedModDescriptor:
    metadata_format = DESCRIPTOR_FORMATS[source]
    value = parse_document(data, metadata_format)
    if metadata_format == "fabric_json":
        parsed = parse_fabric(value, source, chain)
    elif metadata_format == "quilt_json":
        parsed = parse_quilt(value, source, chain)
    elif metadata_format.endswith("toml"):
        parsed = parse_toml(value, source, chain, manifest)
    else:
        parsed = parse_legacy(value, source, chain)
    diagnostics = list(parsed.diagnostics)
    if not parsed.mods:
        diagnostics.append(ModDiagnostic("empty_descriptor", "No mod records declared", source, chain))
    for record in parsed.mods:
        if not record.mod_id:
            diagnostics.append(ModDiagnostic("missing_mod_id", "Mod ID is absent or not a string", source, chain))
        elif record.metadata_format != "forge_legacy_json":
            pattern = r"[a-z][a-z0-9_-]{1,63}" if record.metadata_format == "fabric_json" else r"[a-z][a-z0-9_]{1,63}"
            if re.fullmatch(pattern, record.mod_id) is None:
                diagnostics.append(ModDiagnostic("invalid_mod_id", "Declared mod ID does not follow the loader's ID syntax", source, chain))
        if not record.version:
            diagnostics.append(ModDiagnostic("unresolved_version" if "${" in record.raw_version else "missing_version", "Mod version is absent or unresolved", source, chain))
        if len(record.loaders) > 1:
            diagnostics.append(ModDiagnostic("ambiguous_loader", "mods.toml does not unambiguously identify Forge or early NeoForge", source, chain))
    return replace(parsed, diagnostics=tuple(diagnostics))
