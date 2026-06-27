# Format of dumped Android string resources

## Shorter version without configuration values
```commandline
aapt2 dump resources app-debug.apk --no-values
```

Output:
```text
  type string id=0e entryCount=192
    resource 0x7f0e0000 string/add_new_word
    ...
    resource 0x7f0e00bf string/your_score
```
This is the fully qualified Android Resource ID, broken into 3 segments:    
```text
0x  7f    0e    00bf
    │      │      │
  Package  Type  Entry Index
   (8bit) (8bit) (16bit)
```

Segments can be explained to:

| Segment | Value |                                      Meaning                                       |
|:--------|:--------:|:----------------------------------------------------------------------------------:|
| 0x7f    | Package ID |               0x7f = app's own resources (vs 0x01 = Android system)                |
| 0e      | Type ID |                         Resource type index (here: string)                         |
| 00bf    | Entry index = 0xBF | Position of your_score within the string type (0-based, so it's the 192nd string)  | 


## Longer version having locale configuration values
```commandline
aapt2 dump resources app-debug.apk
```
Output:
```text
  type string id=0e entryCount=192
    resource 0x7f0e0000 string/add_new_word
      () "Add New Words"
      (pl) "Dodaj nowe słowa"
      (en-rGB) "Add New Word"
    ...
  type style id=0f entryCount=56    
```
### format explanation

Each resource entry follows this structure:
```text
resource <hex_id> <type>/<name>
  (<locale>) "<value>"
```

#### Resource declaration line
| Part | Example | Meaning |
|:-----|:--------|:--------|
| `resource` | `resource` | Keyword indicating a resource entry |
| `<hex_id>` | `0x7f0e0000` | Fully qualified resource ID (package + type + entry index) |
| `<type>/<name>` | `string/add_new_word` | Resource type and its name |

#### Configuration (locale) lines


| Entry | Locale | Source file | Meaning |
|:------|:-------|:------------|:--------|
| `()` | Default / fallback | `res/values/strings.xml` | Used when no better locale match is found |
| `(pl)` | Polish | `res/values-pl/strings.xml` | Used for Polish locale |
| `(en-rGB)` | British English | `res/values-en-rGB/strings.xml` | Used for British English locale (`r` prefix is Android's region notation) |
