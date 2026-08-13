# Contributing

## Development workflow

1. Create a focused branch from the default branch.
2. Keep credentials in ignored environment files; update `.env.example` when adding configuration.
3. Make the smallest change that solves the issue.
4. Run the relevant backend and frontend checks.
5. Open a pull request with the reason for the change, test evidence, and any deployment impact.

## Required checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe test_pipeline.py
Set-Location frontend
npm run lint
npm run build
```

Backend tests must not make live LLM or storage calls. Add deterministic tests for new content, layout, and rendering behavior where practical.

## Pull requests

- Keep unrelated formatting or refactoring out of feature and fix branches.
- Describe new environment variables and add safe placeholders to the appropriate `.env.example` file.
- Never include customer documents, generated presentations, uploaded files, logs, access keys, connection strings, or tokens.
- Include screenshots for meaningful UI changes and note any manual validation performed on generated decks.
- Do not commit dependency directories or build output.

## Commit messages

Use short, imperative subjects such as `Add upload validation` or `Fix title overflow`. Explain the motivation in the commit body when the change is not self-evident.
