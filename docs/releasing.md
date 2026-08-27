# Release packaging

NoveltyAudit is distributed as an Agent Skill directory, not as an importable PyPI library. The root `pyproject.toml` provides project metadata and test configuration; setuptools package discovery is explicitly disabled so ignored local work cannot enter a wheel.

Create downloadable source archives only from tracked Git content:

```bash
git archive --format=zip --prefix=NoveltyAudit-v0.3.0/ --output=NoveltyAudit-v0.3.0.zip v0.3.0
```

Never publish an archive made directly from the working directory. It may contain ignored caches, temporary collision scans, PDF renders, smoke-test output, or other local material.
