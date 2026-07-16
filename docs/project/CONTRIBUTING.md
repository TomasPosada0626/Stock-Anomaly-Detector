# Contributing Guide

Thanks for your interest in contributing.

## Workflow

1. Fork the repository.
2. Create a branch from `main`.
3. Implement your change.
4. Add or update tests.
5. Run tests locally.
6. Open a Pull Request with a clear description.

## Branch Naming

Use short, descriptive names:
- `feature/add-lstm-method`
- `fix/dbscan-edge-case`
- `docs/update-readme`

## Code Style

- Keep functions small and readable.
- Prefer descriptive variable names.
- Add comments only when logic is not obvious.
- Preserve existing project structure under `src/`.

## Tests

Run:

```bash
pytest
```

If you add a new anomaly method, include at least:
- One normal-case test
- One edge-case test
- One failure-mode or robustness test

## Documentation

Update relevant docs when behavior changes:
- `README.md`
- `docs/guides/FAQ.md`
- `docs/operations/DEPLOYMENT.md`
- `docs/project/CHANGELOG.md`

## Pull Request Checklist

- [ ] Code runs locally
- [ ] Tests pass
- [ ] New tests added where needed
- [ ] Documentation updated
- [ ] Changelog updated (if relevant)
