# Synthetic Case 001: a killer paper outside the bibliography

**Type:** `SYNTHETIC`

**Failure mode:** `MISSING_KILLER_PAPER`

**Performance status:** Contract fixture, not a benchmark result

## Target

The fictional target claims an architecture that combines adaptive memory with compression-aware selection. Its supplied bibliography contains Paper B, which covers compression-aware selection, but omits Paper A, which covers adaptive memory.

The existing golden fixture also includes Paper C as evidence that A and B belonged to a shared design space before the cutoff. Paper C is bridge evidence; it is not a member of the two-paper Minimal Prior Set.

## Expected audit behavior

- Recover omitted Paper A in the Top-5 killer candidates.
- Mark Paper A `NOT_IN_BIBLIOGRAPHY` and Paper B `IN_BIBLIOGRAPHY`.
- Test the two-paper set A + B as an MPS rather than pretending either paper is a direct precedent.
- Keep Paper C separate as the bridge source.
- Preserve the residual question: whether the target's exact interaction rule remains distinct.

## Gold and source boundary

This is a designed synthetic case reproduced from the repository's [golden composition fixture](../../../scholarly-novelty-audit/tests/fixtures/composition-report.json). All titles, evidence spans, URLs, and identifiers in that fixture are fictional. It tests output semantics and validator behavior only; it says nothing about real-world retrieval performance.

Machine-readable record: [`case.json`](case.json).
