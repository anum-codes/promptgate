# Contributing

Thanks for helping improve promptgate!

```bash
git clone https://github.com/anum-codes/promptgate.git
cd promptgate
pip install -e ".[dev]"
pytest
```

- Add a test for every new assertion or provider (see `tests/`).
- Keep dependencies minimal; the core relies only on PyYAML and the standard library.
- Open an issue before large changes so we can agree on the approach.
