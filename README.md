# Picky

Reusable GitHub Action and workflow templates for Picky pull request review.

The review action now auto-detects changed-file languages, expands scoped codebase context, and supports built-in OpenAI-compatible providers with `deepseek` as the default.

## What is in this repo

- `.github/actions/ai-pr-review/`: the review action implementation
- `.github/workflows/ai-pr-review.yml`: dogfood workflow for this repo
- `.github/workflows/ai-pr-review-reusable.yml`: reusable workflow other repos can call
- `.ai-code-review.yml`: default repo-level review policy template
- `tests/ai_pr_review/`: unit tests for the review engine

## Quick start

The easiest way for another repository to adopt Picky is to call the reusable workflow in this repo.

1. Add provider configuration in the consuming repository or organization.
   API keys go in GitHub `Secrets`.
   Base URLs and model names usually go in GitHub `Variables`.

   DeepSeek example:
   - Secret: `DEEPSEEK_API_KEY`
   - Variable: `DEEPSEEK_BASE_URL`
   - Variable: `DEEPSEEK_CODER_MODEL`

   Other built-in providers:
   - `bcp`: `BCP_API_KEY`, `BCP_BASE_URL`, `BCP_CODER_MODEL`
   - `openai`: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CODER_MODEL`

2. If `picky` is private, allow reusable workflow access from the consuming repository.
   In the `picky` repo, go to `Settings` -> `Actions` -> `General` and allow other repositories in the organization to use its reusable workflows.

3. Copy [.ai-code-review.yml](/Users/kainan/projects/picky/.ai-code-review.yml) into the consuming repository root.
   Adjust exclude rules or prompt guidance only if the defaults do not fit your repo.
   To publish review text in Chinese, set:
   `review.output.language: zh-CN`

4. Add a workflow like this to the consuming repository at `.github/workflows/picky-review.yml`:

```yaml
name: Picky

on:
  pull_request:
    types: [opened, synchronize, ready_for_review]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    uses: layerone-labs/picky/.github/workflows/ai-pr-review-reusable.yml@main
    with:
      provider: deepseek
      config_path: .ai-code-review.yml
      max_files: 25
      max_patch_chars: 120000
      post_summary: true
      min_severity_to_publish: low
    secrets:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
```

5. Open or update a pull request in the consuming repository.
   Picky will detect changed-file languages automatically, gather scoped repo context, and post one batched review with inline comments when it finds issues.

If you fork this repo, the reusable workflow resolves its own source automatically. Consumers can call the forked workflow and it will use the matching forked action code without any internal org-name edits.

## Local validation

```bash
python3 -m unittest discover -s tests -t .
python3 -m compileall .github/actions/ai-pr-review/src tests/ai_pr_review
```
