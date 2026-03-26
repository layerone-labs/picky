# Picky

Reusable GitHub Action and workflow templates for AI-assisted pull request review.

## What is in this repo

- `.github/actions/ai-pr-review/`: the review action implementation
- `.github/workflows/ai-pr-review.yml`: dogfood workflow for this repo
- `.github/workflows/ai-pr-review-reusable.yml`: reusable workflow other repos can call
- `.ai-code-review.yml`: default repo-level review policy template
- `tests/ai_pr_review/`: unit tests for the review engine

## Quick start

1. Add an API key secret named `OPENAI_API_KEY` to a repository.
2. Copy `.ai-code-review.yml` into that repository and adjust include/exclude rules.
3. Either:
   - copy the PR workflow pattern from `.github/workflows/ai-pr-review.yml`, or
   - call `.github/workflows/ai-pr-review-reusable.yml` from that repository.
4. Replace `OWNER/picky` in reusable workflow references after this repo has a real GitHub remote.

## Local validation

```bash
python3 -m unittest discover -s tests -t .
python3 -m compileall .github/actions/ai-pr-review/src tests/ai_pr_review
```
