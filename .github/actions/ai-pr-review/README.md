# AI PR Review Action

Reusable GitHub Action for AI-assisted pull request review.

## What it does

- Reads the pull request diff from GitHub.
- Filters files with configurable include/exclude rules.
- Skips binary, generated, and oversized patches.
- Sends chunked diff context to a provider adapter.
- Normalizes model output into a stable finding schema.
- Publishes inline review comments when line anchors are available.
- Falls back to a summary comment when inline placement is not possible.

## Inputs

- `provider`: provider name. `openai` is implemented first.
- `model`: model name passed to the provider adapter.
- `api_key`: API key for the provider.
- `config_path`: repository policy file, default `.ai-code-review.yml`.
- `max_files`: maximum changed files to review.
- `max_patch_chars`: maximum chars per prompt chunk.
- `post_summary`: whether to post a summary comment.
- `min_severity_to_publish`: minimum severity to publish.

## Example workflow

Use the reusable workflow example in [`reusable-workflow.example.yml`](./reusable-workflow.example.yml) or call the action directly:

```yaml
name: AI PR Review
on:
  pull_request:
    types: [opened, synchronize, ready_for_review]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/ai-pr-review
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }}
```

## Repository policy file

Create `.ai-code-review.yml` in the repository root to customize path filtering, context files, prompt guidance, and severity defaults.

The supported schema matches the nested structure used by the repo template:

```yaml
version: 1

review:
  paths:
    include:
      - "**/*.py"
      - "**/*.js"
    exclude:
      - "**/dist/**"
  generated:
    exclude:
      - "**/*.generated.*"
      - "**/*.snap"
  limits:
    max_files: 25
    max_patch_chars: 120000
  reporting:
    min_severity: low
  prompt:
    extensions:
      - "Prioritize correctness, regressions, security, data loss, concurrency, API misuse, missing tests, and maintainability over style nitpicks."
      - "Only report findings supported by the diff or nearby repository context."
```

Legacy flat keys like `include_paths` and `max_files` are still accepted for compatibility, but the nested schema above is the documented shape.
