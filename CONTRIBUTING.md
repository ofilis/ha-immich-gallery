# Contributing

Contributions are welcome when they keep the integration local, asynchronous,
least-privileged, and compatible with current Home Assistant APIs.

Before opening a pull request:

1. Add or update tests.
2. Run `ruff check .`.
3. Run `ruff format --check .`.
4. Run `python -m pytest`.
5. Confirm that diagnostics contain no credentials, URLs, identifiers,
   filenames, EXIF data, or other personal information.
6. Confirm that API keys remain in headers and are never placed in URLs.
7. If UI behavior changed, attach only screenshots made with example hosts,
   synthetic media, and redacted identifiers.

This is a clean-room implementation. Do not paste code from another custom
integration unless its license is compatible, its origin is documented, and
the required attribution is included.
