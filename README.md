# Picky

Reusable GitHub Action and workflow templates for AI-assisted pull request review.

The review action now auto-detects changed-file languages, expands scoped codebase context, and supports built-in OpenAI-compatible providers with `deepseek` as the default.

## What is in this repo

- `.github/actions/ai-pr-review/`: the review action implementation
- `.github/workflows/ai-pr-review.yml`: dogfood workflow for this repo
- `.github/workflows/ai-pr-review-reusable.yml`: reusable workflow other repos can call
- `.ai-code-review.yml`: default repo-level review policy template
- `tests/ai_pr_review/`: unit tests for the review engine

## Quick start

1. Add provider-native secrets and vars to a repository, such as `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_CODER_MODEL`.
2. Copy `.ai-code-review.yml` into that repository and adjust exclude rules or context settings if needed.
3. Either:
   - copy the PR workflow pattern from `.github/workflows/ai-pr-review.yml`, or
   - call `.github/workflows/ai-pr-review-reusable.yml` from that repository.
4. Use `layerone-labs/picky` in reusable workflow references, or pin to a specific commit SHA or tag for stability.

## Local validation

```bash
python3 -m unittest discover -s tests -t .
python3 -m compileall .github/actions/ai-pr-review/src tests/ai_pr_review
```
