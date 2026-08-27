# Release packaging

NoveltyAudit is distributed as an Agent Skill directory, not as an importable PyPI library. The root `pyproject.toml` provides project metadata and test configuration; setuptools package discovery is explicitly disabled so ignored local work cannot enter a wheel.

Build the installable runtime ZIP with the allowlist-based builder. It includes the repository's complete Apache-2.0 `LICENSE` plus `SKILL.md`, `agents/`, `assets/`, `references/`, `schemas/`, `scripts/`, and `requirements.txt`; tests, benchmarks, caches, temporary scans, and repository metadata are excluded. The build is byte-for-byte deterministic and emits a SHA-256 sidecar with an explicit LF line ending on every platform.

```bash
python tools/build_runtime_bundle.py \
  --skill scholarly-novelty-audit \
  --output dist/scholarly-novelty-audit-v0.3.1.zip
```

If a complete source archive is also desired for developers, create it only from tracked Git content:

```bash
git archive --format=zip --prefix=NoveltyAudit-v0.3.1/ --output=NoveltyAudit-v0.3.1.zip v0.3.1
```

Never publish an archive made directly from the working directory. It may contain ignored caches, temporary collision scans, PDF renders, smoke-test output, or other local material. Upload the runtime ZIP for skill installation and the source archive only as a separate developer artifact.

For a tagged release, push `main` first and then push the annotated `v0.3.1` tag. The release workflow first requires clean runtime installation on both GitHub-hosted Ubuntu and macOS, then reruns the complete test suite, validates the Agent Skill with `skills-ref`, rebuilds the deterministic runtime ZIP, verifies its embedded `LICENSE` and checksum, and creates the GitHub Release with only the runtime ZIP and SHA-256 sidecar. Do not upload the local development RAR or the metadata-only wheel.
