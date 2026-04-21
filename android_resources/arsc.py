"""Binary parser for Android resources.arsc files.

The resources.arsc binary layout (all integers are little-endian):

    ResTable_header          (12 bytes)
    ResStringPool            (global value string pool)
    ResTable_package ...     (one per package)
        ResStringPool        (type-name string pool)
        ResStringPool        (resource-key string pool)
        ResTable_typeSpec    (one per type)
        ResTable_type ...    (one per type/configuration)

References
----------
* https://android.googlesource.com/platform/frameworks/base/+/master/
  libs/androidfw/include/androidfw/ResourceTypes.h
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Chunk type constants
# ---------------------------------------------------------------------------
_RES_STRING_POOL_TYPE = 0x0001
_RES_TABLE_TYPE = 0x0002
_RES_TABLE_PACKAGE_TYPE = 0x0200
_RES_TABLE_TYPE_SPEC_TYPE = 0x0202
_RES_TABLE_TYPE_TYPE = 0x0201

# String pool flags
_UTF8_FLAG = 1 << 8

# ResTable_value data types
_TYPE_NULL = 0x00
_TYPE_REFERENCE = 0x01
_TYPE_STRING = 0x03

# ResTable_entry flags
_FLAG_COMPLEX = 0x0001

# Sentinel for missing entries
_NO_ENTRY = 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class StringPool:
    """Represents a parsed ResStringPool chunk."""

    strings: list[str] = field(default_factory=list)
    """All decoded strings in pool order."""

    is_utf8: bool = False
    """True if the pool uses UTF-8 encoding (otherwise UTF-16LE)."""

    def __getitem__(self, index: int) -> str:
        return self.strings[index]

    def __len__(self) -> int:
        return len(self.strings)

    def __iter__(self):
        return iter(self.strings)


@dataclass
class StringResource:
    """A single parsed string resource entry."""

    resource_id: int
    """Full 32-bit Android resource ID (e.g. 0x7F040001)."""

    package_id: int
    """Package portion of the resource ID (high byte)."""

    type_id: int
    """Type portion of the resource ID."""

    entry_index: int
    """Entry index within the type."""

    key: str
    """Resource name (key), e.g. ``"app_name"``."""

    value: str
    """String value."""


@dataclass
class Package:
    """Represents a parsed ResTable_package chunk."""

    id: int = 0
    """Package ID (0x01 for system, 0x7F for application)."""

    name: str = ""
    """Java-style package name, e.g. ``"com.example.app"``."""

    type_string_pool: StringPool = field(default_factory=StringPool)
    """String pool that maps type IDs to type names (e.g. ``"string"``)."""

    key_string_pool: StringPool = field(default_factory=StringPool)
    """String pool that maps key indices to resource names."""

    string_resources: list[StringResource] = field(default_factory=list)
    """All ``string`` type resources found in this package."""


@dataclass
class ResourceTable:
    """Represents a fully parsed resources.arsc file."""

    global_string_pool: StringPool = field(default_factory=StringPool)
    """Global value string pool (contains actual string values)."""

    packages: list[Package] = field(default_factory=list)
    """All packages embedded in the table."""

    @property
    def string_resources(self) -> list[StringResource]:
        """Flat list of all string resources across all packages."""
        result: list[StringResource] = []
        for pkg in self.packages:
            result.extend(pkg.string_resources)
        return result


# ---------------------------------------------------------------------------
# Low-level binary helpers
# ---------------------------------------------------------------------------


def _u8(data: bytes, pos: int) -> int:
    return data[pos]


def _u16(data: bytes, pos: int) -> int:
    return struct.unpack_from("<H", data, pos)[0]


def _u32(data: bytes, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def _read_utf8_length(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a variable-length integer used in UTF-8 string pools.

    Returns ``(value, bytes_consumed)``.
    """
    byte = data[pos]
    if byte & 0x80:
        return ((byte & 0x7F) << 8) | data[pos + 1], 2
    return byte, 1


def _read_utf16_length(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a variable-length integer used in UTF-16 string pools.

    Returns ``(value_in_code_units, bytes_consumed)``.
    """
    unit = _u16(data, pos)
    if unit & 0x8000:
        return ((unit & 0x7FFF) << 16) | _u16(data, pos + 2), 4
    return unit, 2


# ---------------------------------------------------------------------------
# String-pool parser
# ---------------------------------------------------------------------------


def _parse_string_utf8(data: bytes, abs_offset: int) -> str:
    """Decode a single UTF-8 string starting at *abs_offset* in *data*."""
    pos = abs_offset
    # UTF-16 char count (skip – we only need byte count)
    _, skip = _read_utf8_length(data, pos)
    pos += skip
    byte_len, skip = _read_utf8_length(data, pos)
    pos += skip
    return data[pos : pos + byte_len].decode("utf-8", errors="replace")


def _parse_string_utf16(data: bytes, abs_offset: int) -> str:
    """Decode a single UTF-16LE string starting at *abs_offset* in *data*."""
    char_count, skip = _read_utf16_length(data, abs_offset)
    start = abs_offset + skip
    return data[start : start + char_count * 2].decode("utf-16-le", errors="replace")


def parse_string_pool(data: bytes, base: int = 0) -> StringPool:
    """Parse a *ResStringPool* chunk at byte offset *base* in *data*.

    Parameters
    ----------
    data:
        Raw bytes of the containing chunk (or the whole file).
    base:
        Byte offset at which the string pool chunk starts.

    Returns
    -------
    StringPool
        Parsed string pool with ``strings`` list populated.
    """
    chunk_type = _u16(data, base)
    if chunk_type != _RES_STRING_POOL_TYPE:
        raise ValueError(
            f"Expected RES_STRING_POOL_TYPE (0x0001), got 0x{chunk_type:04x} at offset {base}"
        )
    header_size = _u16(data, base + 2)
    string_count = _u32(data, base + 8)
    flags = _u32(data, base + 16)
    strings_start = _u32(data, base + 20)

    is_utf8 = bool(flags & _UTF8_FLAG)
    pool = StringPool(is_utf8=is_utf8)

    # Offset table immediately follows the header
    offsets_start = base + header_size
    # Absolute start of the raw string data
    strings_data_base = base + strings_start

    for i in range(string_count):
        offset = _u32(data, offsets_start + i * 4)
        abs_pos = strings_data_base + offset
        if is_utf8:
            s = _parse_string_utf8(data, abs_pos)
        else:
            s = _parse_string_utf16(data, abs_pos)
        pool.strings.append(s)

    return pool


# ---------------------------------------------------------------------------
# Package parser
# ---------------------------------------------------------------------------


def _parse_package(data: bytes, base: int, global_pool: StringPool) -> Package:
    """Parse a *ResTable_package* chunk at *base*.

    The *global_pool* is needed to look up string values for ``TYPE_STRING``
    entries.
    """
    # ResTable_package header layout:
    #   0  ResChunk_header (8 bytes): type(2), headerSize(2), size(4)
    #   8  id           uint32
    #  12  name         char16_t[128]  = 256 bytes
    # 268  typeStrings  uint32  offset from package start
    # 272  lastPublicType uint32
    # 276  keyStrings   uint32  offset from package start
    # 280  lastPublicKey uint32
    # 284  typeIdOffset uint32
    pkg_id = _u32(data, base + 8)
    name_raw = data[base + 12 : base + 12 + 256]
    name = name_raw.decode("utf-16-le", errors="replace").rstrip("\x00")

    type_strings_off = _u32(data, base + 268)
    key_strings_off = _u32(data, base + 276)

    package = Package(id=pkg_id, name=name)

    if type_strings_off:
        package.type_string_pool = parse_string_pool(data, base + type_strings_off)
    if key_strings_off:
        package.key_string_pool = parse_string_pool(data, base + key_strings_off)

    # Find "string" type index (1-based in the type pool → id)
    string_type_indices: list[int] = [
        i for i, t in enumerate(package.type_string_pool.strings) if t == "string"
    ]

    # Walk sub-chunks inside the package
    header_size = _u16(data, base + 2)
    chunk_size = _u32(data, base + 4)
    pos = base + header_size
    end = base + chunk_size

    # Collect typeSpec flags and type chunks
    type_specs: dict[int, bytes] = {}

    while pos < end:
        if pos + 8 > len(data):
            break
        c_type = _u16(data, pos)
        c_size = _u32(data, pos + 4)
        if c_size == 0:
            break

        if c_type == _RES_TABLE_TYPE_SPEC_TYPE:
            spec_id = _u8(data, pos + 8)
            type_specs[spec_id] = data[pos : pos + c_size]

        elif c_type == _RES_TABLE_TYPE_TYPE:
            type_id = _u8(data, pos + 8)  # 1-based
            # type_index = type_id - 1 (0-based index into type string pool)
            type_index = type_id - 1
            if type_index in string_type_indices:
                entries = _parse_type_chunk(
                    data,
                    pos,
                    pkg_id,
                    type_id,
                    package.key_string_pool,
                    global_pool,
                )
                package.string_resources.extend(entries)

        pos += c_size

    return package


def _parse_type_chunk(
    data: bytes,
    base: int,
    pkg_id: int,
    type_id: int,
    key_pool: StringPool,
    value_pool: StringPool,
) -> list[StringResource]:
    """Parse a *ResTable_type* chunk and return string resource entries.

    Only entries with ``dataType == TYPE_STRING`` are returned; entries with
    other value types (e.g. references) are skipped.
    """
    # ResTable_type header:
    #  0  ResChunk_header (8)
    #  8  id (1), flags (1), reserved (2)
    # 12  entryCount  uint32
    # 16  entriesStart uint32   offset from chunk start to entry data
    # 20  config       ResTable_config (size is its first uint32)

    header_size = _u16(data, base + 2)
    entry_count = _u32(data, base + 12)
    entries_start = _u32(data, base + 16)

    # Offset array: immediately after the header
    offsets_array_start = base + header_size
    # Absolute start of entry data
    entries_base = base + entries_start

    results: list[StringResource] = []

    for entry_index in range(entry_count):
        raw_offset = _u32(data, offsets_array_start + entry_index * 4)
        if raw_offset == _NO_ENTRY:
            continue

        entry_pos = entries_base + raw_offset
        entry_size = _u16(data, entry_pos)
        entry_flags = _u16(data, entry_pos + 2)
        key_index = _u32(data, entry_pos + 4)

        if entry_flags & _FLAG_COMPLEX:
            # Map entry – not a simple value, skip
            continue

        # Res_value follows the entry header
        value_pos = entry_pos + entry_size
        # value: size(2), res0(1), dataType(1), data(4)
        data_type = _u8(data, value_pos + 3)
        value_data = _u32(data, value_pos + 4)

        if data_type != _TYPE_STRING:
            continue

        key_name = key_pool.strings[key_index] if key_index < len(key_pool) else ""
        value_str = value_pool.strings[value_data] if value_data < len(value_pool) else ""

        resource_id = (pkg_id << 24) | (type_id << 16) | entry_index
        results.append(
            StringResource(
                resource_id=resource_id,
                package_id=pkg_id,
                type_id=type_id,
                entry_index=entry_index,
                key=key_name,
                value=value_str,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------


def parse_resource_table(data: bytes) -> ResourceTable:
    """Parse a complete *resources.arsc* binary and return a :class:`ResourceTable`.

    Parameters
    ----------
    data:
        Raw bytes of the ``resources.arsc`` file.

    Returns
    -------
    ResourceTable
        Structured representation of the resource table, including the global
        string pool and all discovered ``string`` type resources.

    Raises
    ------
    ValueError
        If *data* does not start with a valid ``ResTable`` chunk header.
    """
    if len(data) < 12:
        raise ValueError("Data too short to be a valid resources.arsc file")

    chunk_type = _u16(data, 0)
    if chunk_type != _RES_TABLE_TYPE:
        raise ValueError(
            f"Not a resource table: expected chunk type 0x0002, got 0x{chunk_type:04x}"
        )

    header_size = _u16(data, 2)
    table_size = _u32(data, 4)

    table = ResourceTable()
    pos = header_size

    # Global string pool must immediately follow the table header
    if pos < table_size and _u16(data, pos) == _RES_STRING_POOL_TYPE:
        sp_size = _u32(data, pos + 4)
        table.global_string_pool = parse_string_pool(data, pos)
        pos += sp_size

    # Parse package chunks
    while pos < table_size:
        if pos + 8 > len(data):
            break
        c_type = _u16(data, pos)
        c_size = _u32(data, pos + 4)
        if c_size == 0:
            break
        if c_type == _RES_TABLE_PACKAGE_TYPE:
            pkg = _parse_package(data, pos, table.global_string_pool)
            table.packages.append(pkg)
        pos += c_size

    return table
