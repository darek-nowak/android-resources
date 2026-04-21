# android-resources

Reverse-engineer the **string table** from an Android `resources.arsc` binary file.

## What is `resources.arsc`?

Every Android APK contains a compiled binary resource table (`resources.arsc`).
It stores all app resources – including *string* values – in a compact binary
format.  This library parses that format and exposes the string table as
structured Python objects.

## Installation

```bash
pip install .
```

Requires Python 3.9 or newer.  No third-party dependencies.

## Quick start

### Command-line

```bash
# Extract all string resources (key → value)
arsc-strings path/to/resources.arsc

# JSON output
arsc-strings path/to/resources.arsc --format json

# Dump the raw global string pool (all value strings)
arsc-strings path/to/resources.arsc --pool
```

Example output:

```
0x7f040000  'app_name'                               = 'My Application'
0x7f040001  'hello_world'                            = 'Hello World!'
```

### Python API

```python
from android_resources import parse_resource_table

with open("resources.arsc", "rb") as f:
    table = parse_resource_table(f.read())

# All string resources across all packages
for res in table.string_resources:
    print(f"0x{res.resource_id:08x}  {res.key} = {res.value!r}")

# Raw global string pool
for i, s in enumerate(table.global_string_pool):
    print(i, s)

# Per-package details
for pkg in table.packages:
    print(f"Package: {pkg.name}  (id=0x{pkg.id:02x})")
    print("  Types:", pkg.type_string_pool.strings)
    print("  Keys:",  pkg.key_string_pool.strings)
```

## Binary format overview

```
resources.arsc
├── ResTable_header            (12 bytes)
├── ResStringPool              global value string pool
└── ResTable_package …         one entry per package
    ├── ResStringPool          type-name string pool  ("string", "layout", …)
    ├── ResStringPool          resource-key string pool  ("app_name", …)
    ├── ResTable_typeSpec …
    └── ResTable_type …        one per type/configuration; entries reference
                               the global string pool by index
```

All integers are **little-endian**.

## Running tests

```bash
pip install pytest
pytest
```
