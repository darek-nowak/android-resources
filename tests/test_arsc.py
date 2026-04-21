"""Tests for the resources.arsc parser."""

from __future__ import annotations

import struct

import pytest

from android_resources import parse_resource_table, StringPool
from android_resources.arsc import parse_string_pool
from tests.conftest import (
    build_minimal_arsc,
    _build_string_pool_utf8,
    _encode_utf8_str,
)


# ---------------------------------------------------------------------------
# StringPool – UTF-8 encoding helpers
# ---------------------------------------------------------------------------


class TestEncodeUtf8Str:
    def test_simple_ascii(self):
        raw = _encode_utf8_str("hello")
        # char_len=5 (1 byte), byte_len=5 (1 byte), b"hello", null
        assert raw == b"\x05\x05hello\x00"

    def test_empty_string(self):
        raw = _encode_utf8_str("")
        assert raw == b"\x00\x00\x00"

    def test_multibyte_utf8(self):
        # "é" is 2 UTF-8 bytes but 1 UTF-16 char
        raw = _encode_utf8_str("é")
        char_len_byte = raw[0]
        byte_len_byte = raw[1]
        assert char_len_byte == 1
        assert byte_len_byte == 2
        assert raw[2:4] == "é".encode("utf-8")
        assert raw[4] == 0  # null terminator

    def test_long_string_uses_two_byte_length(self):
        # Strings with >= 128 chars need the 2-byte variable-length encoding
        s = "x" * 200
        raw = _encode_utf8_str(s)
        # First byte should have high bit set (0x80 | 0)
        assert raw[0] & 0x80, "Expected 2-byte length for char_len >= 128"


# ---------------------------------------------------------------------------
# StringPool – pool builder & parser round-trip
# ---------------------------------------------------------------------------


class TestStringPoolUtf8:
    def test_empty_pool(self):
        pool_bytes = _build_string_pool_utf8([])
        pool = parse_string_pool(pool_bytes, 0)
        assert pool.strings == []
        assert pool.is_utf8 is True

    def test_single_string(self):
        pool_bytes = _build_string_pool_utf8(["hello"])
        pool = parse_string_pool(pool_bytes, 0)
        assert pool.strings == ["hello"]

    def test_multiple_strings(self):
        strings = ["Hello, World!", "App Name", ""]
        pool_bytes = _build_string_pool_utf8(strings)
        pool = parse_string_pool(pool_bytes, 0)
        assert pool.strings == strings

    def test_unicode_strings(self):
        strings = ["Héllo", "世界", "日本語テスト"]
        pool_bytes = _build_string_pool_utf8(strings)
        pool = parse_string_pool(pool_bytes, 0)
        assert pool.strings == strings

    def test_wrong_chunk_type_raises(self):
        # Corrupt the first two bytes (chunk type)
        pool_bytes = bytearray(_build_string_pool_utf8(["hi"]))
        pool_bytes[0] = 0xFF
        pool_bytes[1] = 0xFF
        with pytest.raises(ValueError, match="RES_STRING_POOL_TYPE"):
            parse_string_pool(bytes(pool_bytes), 0)

    def test_pool_at_nonzero_offset(self):
        """Pool can be embedded at an arbitrary offset in a larger buffer."""
        prefix = b"\xDE\xAD\xBE\xEF" * 4  # 16-byte garbage prefix
        pool_bytes = _build_string_pool_utf8(["offset_test"])
        buf = prefix + pool_bytes
        pool = parse_string_pool(buf, len(prefix))
        assert pool.strings == ["offset_test"]

    def test_subscript_and_iteration(self):
        strings = ["a", "b", "c"]
        pool_bytes = _build_string_pool_utf8(strings)
        pool = parse_string_pool(pool_bytes, 0)
        assert pool[0] == "a"
        assert pool[2] == "c"
        assert list(pool) == strings
        assert len(pool) == 3


# ---------------------------------------------------------------------------
# parse_resource_table – error handling
# ---------------------------------------------------------------------------


class TestParseResourceTableErrors:
    def test_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            parse_resource_table(b"\x02\x00")

    def test_wrong_magic(self):
        data = b"\xFF\xFF" + b"\x00" * 10
        with pytest.raises(ValueError, match="0x0002"):
            parse_resource_table(data)


# ---------------------------------------------------------------------------
# Minimal arsc round-trip
# ---------------------------------------------------------------------------


class TestMinimalArsc:
    def test_global_pool_strings(self, minimal_arsc_table):
        pool = minimal_arsc_table.global_string_pool
        assert "Hello, World!" in pool.strings
        assert "App Name" in pool.strings

    def test_single_package(self, minimal_arsc_table):
        assert len(minimal_arsc_table.packages) == 1

    def test_package_id(self, minimal_arsc_table):
        assert minimal_arsc_table.packages[0].id == 0x7F

    def test_package_name(self, minimal_arsc_table):
        assert minimal_arsc_table.packages[0].name == "com.example"

    def test_type_pool(self, minimal_arsc_table):
        pkg = minimal_arsc_table.packages[0]
        assert "string" in pkg.type_string_pool.strings

    def test_key_pool(self, minimal_arsc_table):
        pkg = minimal_arsc_table.packages[0]
        assert "hello_world" in pkg.key_string_pool.strings
        assert "app_name" in pkg.key_string_pool.strings

    def test_string_resources_count(self, minimal_arsc_table):
        resources = minimal_arsc_table.string_resources
        assert len(resources) == 2

    def test_string_resource_keys_and_values(self, minimal_arsc_table):
        resources = {r.key: r.value for r in minimal_arsc_table.string_resources}
        assert resources["hello_world"] == "Hello, World!"
        assert resources["app_name"] == "App Name"

    def test_resource_ids_are_unique(self, minimal_arsc_table):
        ids = [r.resource_id for r in minimal_arsc_table.string_resources]
        assert len(ids) == len(set(ids))

    def test_resource_id_encodes_package_and_type(self, minimal_arsc_table):
        for r in minimal_arsc_table.string_resources:
            assert (r.resource_id >> 24) & 0xFF == 0x7F  # package id
            assert (r.resource_id >> 16) & 0xFF == 1  # type id (string = 1)


# ---------------------------------------------------------------------------
# Custom arsc variations
# ---------------------------------------------------------------------------


class TestCustomArsc:
    def test_multiple_string_resources(self):
        table = parse_resource_table(
            build_minimal_arsc(
                global_strings=["foo", "bar", "baz"],
                key_names=["k0", "k1", "k2"],
                string_entries=[(0, 0), (1, 1), (2, 2)],
            )
        )
        resources = {r.key: r.value for r in table.string_resources}
        assert resources == {"k0": "foo", "k1": "bar", "k2": "baz"}

    def test_empty_string_value(self):
        table = parse_resource_table(
            build_minimal_arsc(
                global_strings=["", "something"],
                key_names=["empty_key"],
                string_entries=[(0, 0)],
            )
        )
        assert table.string_resources[0].value == ""

    def test_unicode_values(self):
        table = parse_resource_table(
            build_minimal_arsc(
                global_strings=["こんにちは", "Héllo"],
                key_names=["greeting_ja", "greeting_fr"],
                string_entries=[(0, 0), (1, 1)],
            )
        )
        resources = {r.key: r.value for r in table.string_resources}
        assert resources["greeting_ja"] == "こんにちは"
        assert resources["greeting_fr"] == "Héllo"

    def test_non_string_package_not_included(self):
        """Packages that contain no 'string' type should yield no string_resources."""
        table = parse_resource_table(
            build_minimal_arsc(
                type_names=["layout"],  # no "string" type
                key_names=["main"],
                string_entries=[(0, 0)],
            )
        )
        assert table.string_resources == []

    def test_flat_string_resources_across_packages(self):
        """ResourceTable.string_resources aggregates across all packages."""
        # Build a table, then verify the property delegates correctly
        table = parse_resource_table(build_minimal_arsc())
        assert table.string_resources == table.packages[0].string_resources
