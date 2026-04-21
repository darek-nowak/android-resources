"""Shared pytest fixtures – notably a minimal-but-valid resources.arsc builder.

Binary layout produced by ``build_minimal_arsc``:

    ResTable_header          (12 bytes)
    ResStringPool  [UTF-8]   (global value pool: "Hello, World!", "App Name", "")
    ResTable_package         (packageCount=1, id=0x7F, name="com.example")
        ResStringPool [UTF-8] (type names: "string")
        ResStringPool [UTF-8] (key names: "hello_world", "app_name")
        ResTable_typeSpec     (1 type, 2 entries)
        ResTable_type         (default config, 2 entries)
            entry 0: key=0 (hello_world) → TYPE_STRING data=0 ("Hello, World!")
            entry 1: key=1 (app_name)    → TYPE_STRING data=1 ("App Name")
"""

from __future__ import annotations

import struct

import pytest


# ---------------------------------------------------------------------------
# Helpers to serialise individual binary structures
# ---------------------------------------------------------------------------


def _encode_utf8_str(s: str) -> bytes:
    """Encode a string for a UTF-8 ResStringPool string section.

    Format: <utf16_charlen> <utf8_bytelen> <utf8_bytes> <0x00>
    Both length fields use the 1- or 2-byte variable-length encoding.
    """
    encoded = s.encode("utf-8")
    char_len = len(s)
    byte_len = len(encoded)

    def _var(n: int) -> bytes:
        if n >= 0x80:
            return bytes([(n >> 8) | 0x80, n & 0xFF])
        return bytes([n])

    return _var(char_len) + _var(byte_len) + encoded + b"\x00"


def _build_string_pool_utf8(strings: list[str]) -> bytes:
    """Build a complete UTF-8 ResStringPool chunk for *strings*."""
    UTF8_FLAG = 1 << 8

    # Encode all strings
    encoded = [_encode_utf8_str(s) for s in strings]

    # Build offset table (each offset relative to the start of string data)
    offsets: list[int] = []
    pos = 0
    for enc in encoded:
        offsets.append(pos)
        pos += len(enc)

    string_data = b"".join(encoded)
    # Pad string data to 4-byte boundary
    pad = (4 - len(string_data) % 4) % 4
    string_data += b"\x00" * pad

    string_count = len(strings)
    header_size = 28  # ResStringPool_header is always 28 bytes
    strings_start = header_size + string_count * 4  # header + offset array
    chunk_size = strings_start + len(string_data)

    header = struct.pack(
        "<HHIIIIII",
        0x0001,         # chunkType = RES_STRING_POOL_TYPE
        header_size,    # headerSize
        chunk_size,     # size
        string_count,   # stringCount
        0,              # styleCount
        UTF8_FLAG,      # flags
        strings_start,  # stringsStart
        0,              # stylesStart
    )
    offset_table = struct.pack(f"<{string_count}I", *offsets)
    return header + offset_table + string_data


def _build_type_spec(type_id: int, entry_count: int) -> bytes:
    """Build a ResTable_typeSpec chunk."""
    # header (8) + id(1) + flags(1) + reserved(2) + entryCount(4) + specs(4*n)
    specs = [0] * entry_count  # all public, no config-specific flags
    header_size = 8
    chunk_size = header_size + 4 + 4 + entry_count * 4
    data = struct.pack(
        "<HHI BBH I",
        0x0202,      # RES_TABLE_TYPE_SPEC_TYPE
        header_size,
        chunk_size,
        type_id,     # id (1 byte)
        0,           # flags (1 byte)
        0,           # reserved (2 bytes)
        entry_count,
    )
    data += struct.pack(f"<{entry_count}I", *specs)
    return data


def _build_res_value(data_type: int, value: int) -> bytes:
    """Build an 8-byte Res_value."""
    return struct.pack("<HBBi", 8, 0, data_type, value)


def _build_entry(key_index: int, data_type: int, value: int) -> bytes:
    """Build a simple (non-complex) ResTable_entry + Res_value (16 bytes total)."""
    entry = struct.pack("<HHI", 8, 0, key_index)   # size=8, flags=0, key
    val = _build_res_value(data_type, value)
    return entry + val


def _build_type_chunk(
    type_id: int,
    entries: list[tuple[int, int, int]],  # (key_index, data_type, data)
) -> bytes:
    """Build a ResTable_type chunk with a minimal (32-byte) default config."""
    entry_count = len(entries)
    config_size = 32
    # header_size = ResChunk_header(8) + id(1)+flags(1)+res(2) + entryCount(4)
    #               + entriesStart(4) + config(32)  = 52
    header_size = 8 + 1 + 1 + 2 + 4 + 4 + config_size
    entries_start = header_size + entry_count * 4  # header + offset array

    # Build entry binary blobs
    entry_blobs = [_build_entry(ki, dt, dv) for ki, dt, dv in entries]

    # Compute offsets within the entries section
    offsets: list[int] = []
    pos = 0
    for blob in entry_blobs:
        offsets.append(pos)
        pos += len(blob)

    entries_data = b"".join(entry_blobs)
    chunk_size = entries_start + len(entries_data)

    # Pack the header fields
    chunk_hdr = struct.pack(
        "<HHI",
        0x0201,      # RES_TABLE_TYPE_TYPE
        header_size,
        chunk_size,
    )
    id_flags = struct.pack("<BBH", type_id, 0, 0)
    counts = struct.pack("<II", entry_count, entries_start)
    # Minimal 32-byte ResTable_config: first uint32 = size, rest zeroed
    config = struct.pack("<I", config_size) + b"\x00" * (config_size - 4)
    offset_table = struct.pack(f"<{entry_count}I", *offsets)

    return chunk_hdr + id_flags + counts + config + offset_table + entries_data


def build_minimal_arsc(
    package_name: str = "com.example",
    package_id: int = 0x7F,
    global_strings: list[str] | None = None,
    type_names: list[str] | None = None,
    key_names: list[str] | None = None,
    string_entries: list[tuple[int, int]] | None = None,
) -> bytes:
    """Build a minimal valid resources.arsc binary in memory.

    Parameters
    ----------
    package_name:
        Java package name for the single embedded package.
    package_id:
        Numeric package ID (0x7F for apps, 0x01 for framework).
    global_strings:
        Values to place in the global string pool.
        Defaults to ``["Hello, World!", "App Name", ""]``.
    type_names:
        Type-name strings (e.g. ``["string"]``).
    key_names:
        Resource-key strings (e.g. ``["hello_world", "app_name"]``).
    string_entries:
        Sequence of ``(key_index, global_pool_index)`` pairs that define
        the string resources.  Each pair produces one entry of
        ``TYPE_STRING`` pointing at the corresponding global pool string.
    """
    if global_strings is None:
        global_strings = ["Hello, World!", "App Name", ""]
    if type_names is None:
        type_names = ["string"]
    if key_names is None:
        key_names = ["hello_world", "app_name"]
    if string_entries is None:
        string_entries = [(0, 0), (1, 1)]  # (key_index, value_index)

    # The type ID for "string" is 1 (1-based index in the type pool, here the
    # only type, so its id byte is 1).
    type_id = 1

    # Build individual chunks
    global_pool_bytes = _build_string_pool_utf8(global_strings)
    type_pool_bytes = _build_string_pool_utf8(type_names)
    key_pool_bytes = _build_string_pool_utf8(key_names)
    type_spec_bytes = _build_type_spec(type_id, len(string_entries))
    type_chunk_bytes = _build_type_chunk(
        type_id,
        [(ki, 0x03, vi) for ki, vi in string_entries],  # 0x03 = TYPE_STRING
    )

    # ResTable_package header (288 bytes)
    pkg_name_utf16 = package_name.encode("utf-16-le").ljust(256, b"\x00")[:256]
    type_strings_off = 288  # immediately after the package header
    key_strings_off = type_strings_off + len(type_pool_bytes)
    pkg_sub_chunks = type_spec_bytes + type_chunk_bytes
    pkg_inner_size = (
        len(type_pool_bytes) + len(key_pool_bytes) + len(pkg_sub_chunks)
    )
    pkg_chunk_size = 288 + pkg_inner_size

    pkg_header = struct.pack(
        "<HHI",
        0x0200,        # RES_TABLE_PACKAGE_TYPE
        288,           # headerSize
        pkg_chunk_size,
    )
    pkg_header += struct.pack("<I", package_id)   # id
    pkg_header += pkg_name_utf16                   # name[128]
    pkg_header += struct.pack(
        "<IIIII",
        type_strings_off,  # typeStrings
        len(type_names) - 1,  # lastPublicType
        key_strings_off,   # keyStrings
        len(key_names) - 1,  # lastPublicKey
        0,                 # typeIdOffset
    )

    package_chunk = (
        pkg_header + type_pool_bytes + key_pool_bytes + pkg_sub_chunks
    )

    # ResTable header (12 bytes)
    table_size = 12 + len(global_pool_bytes) + len(package_chunk)
    table_header = struct.pack(
        "<HHII",
        0x0002,      # RES_TABLE_TYPE
        12,          # headerSize
        table_size,  # size
        1,           # packageCount
    )

    return table_header + global_pool_bytes + package_chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_arsc_bytes() -> bytes:
    """Minimal valid resources.arsc binary with 2 string entries."""
    return build_minimal_arsc()


@pytest.fixture
def minimal_arsc_table(minimal_arsc_bytes):
    """Parsed ResourceTable from the minimal arsc fixture."""
    from android_resources import parse_resource_table

    return parse_resource_table(minimal_arsc_bytes)
