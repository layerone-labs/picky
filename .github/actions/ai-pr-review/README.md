# AI PR Review Action

Reusable GitHub Action for Picky pull request review.

## What it does

- Reads the pull request diff from GitHub.
- Detects changed-file languages automatically with extension, filename, shebang, and light content sniffing.
- Filters files with configurable language and path rules.
- Skips binary, generated, and oversized patches.
- Expands scoped repository context from manifests, related config, imports, and sibling tests.
- Sends chunked diff context to an OpenAI-compatible provider adapter.
- Normalizes model output into a stable finding schema.
- Publishes inline review comments when line anchors are available.
- Falls back to a summary comment when inline placement is not possible.

## Inputs

- `provider`: one of `deepseek`, `bcp`, or `openai`. Default: `deepseek`.
- `model`: optional model name override. Otherwise resolved from provider-native env vars.
- `base_url`: optional provider base URL override.
- `api_key`: optional API key override. Otherwise resolved from provider-native env vars.
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
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          DEEPSEEK_BASE_URL: ${{ vars.DEEPSEEK_BASE_URL }}
          DEEPSEEK_CODER_MODEL: ${{ vars.DEEPSEEK_CODER_MODEL }}
```

When another repository calls the reusable workflow, it automatically checks out the same repo and commit that provided the workflow. Forks do not need to rewrite internal `owner/repo` references.

## Repository policy file

Create `.ai-code-review.yml` in the repository root to customize language filtering, scoped context gathering, prompt guidance, and severity defaults.

The supported schema matches the nested structure used by the repo template:

```yaml
version: 1

review:
  languages:
    mode: auto
    review_unknown_text: false
  context:
    mode: scoped
    max_files: 8
    max_bytes: 32000
    include_tests: true
    include_imports: true
    include_repo_files: true
  paths:
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

Provider-native env names:

- `deepseek`: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_CODER_MODEL`
- `bcp`: `BCP_API_KEY`, `BCP_BASE_URL`, `BCP_CODER_MODEL`
- `openai`: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CODER_MODEL`

Legacy flat keys like `include_paths` and `max_files` are still accepted for compatibility, but the nested schema above is the documented shape.
