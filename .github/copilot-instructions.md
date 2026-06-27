# GitHub Copilot Instructions

## Project Overview
This is a Python project for reverse engineering resource binary table and extracting information about string resources

### Tools used
aapt2 (Android Asset Packaging Tool) tool from android build tools is used to extract the resource table from the APK file. 
https://developer.android.com/tools/aapt2
The extracted resource table is then parsed to retrieve string resources and their corresponding values.
The following command can be used to dump all the sting resources from the APK file:
```commandline
aapt2 dump strings <apk_file>
```

Print all resources from the APK file without values using the following command:
```commandline
$ANDROID_HOME/build-tools/36.1.0/aapt2 dump resources app-debug.apk --no-values
```

Output is explained here [String Resources Explanation](../docs/android_string_resources.md)

/Users/darek/Library/Android/sdk/build-tools/36.1.0/aapt2
$ANDROID_HOME 
$ANDROID_HOME/build-tools/36.1.0/aapt2 


## Language & Environment
- **Language:** Python 3.x
- **IDE:** JetBrains PyCharm
- **Platform target:** Android resource management

## Code Style & Conventions
- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
- Use type hints for all function signatures.
- Write docstrings (Google style) for all public functions and classes.
- Keep functions small and focused on a single responsibility.
- Prefer f-strings over `.format()` or `%` formatting.

## Naming Conventions
- `snake_case` for variables, functions, and module names.
- `PascalCase` for class names.
- `UPPER_SNAKE_CASE` for constants.
- Prefix private members with a single underscore `_`.

## Android Resource Conventions
- Android resource file names should be all lowercase, with underscores as separators (e.g., `ic_launcher.png`, `strings.xml`).
- Resource types to handle: `drawable`, `layout`, `values`, `mipmap`, `menu`, `anim`, `raw`, `font`.
- Density qualifiers: `ldpi`, `mdpi`, `hdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`.
- Configuration qualifiers follow Android naming conventions (e.g., `values-night`, `layout-land`).

## Error Handling
- Use specific exception types; avoid bare `except:` clauses.
- Log errors with the `logging` module rather than `print()` in production code.
- Provide meaningful error messages that help diagnose the problem.

## Testing
- Write unit tests using `pytest`.
- Test files are named `test_<module_name>.py` and placed in a `/tests` directory.

## Dependencies
- Prefer standard library modules when sufficient.
- List all third-party dependencies in `requirements.txt`.
- Pin dependency versions for reproducibility.


