# Strict temporal cutoff

The adverse evidence date is the earliest date on which the work was publicly accessible, not the date most convenient to the verdict.

Prefer complete dates in this order of evidentiary value: preprint v1, first public OpenReview manuscript, accepted manuscript or publisher online-first, Crossref published-online or issued date, then proceedings date. Preserve every observed version date.

If only a year is known, mark `DATE_UNCERTAIN`. Never invent January 1. In strict mode, only `ELIGIBLE` papers may support a direct precedent, MPS, or historical bridge. Keep `POST_CUTOFF` and `DATE_UNCERTAIN` papers in clearly separated report sections.

When versions disagree, use the earliest verified public date and retain provenance for the conflicting values.

Do not rely on a provider's publication-date prefilter for strict history: a journal version may appear after the cutoff while its preprint was public before it. Retrieve candidates, merge versions, then apply the deterministic cutoff resolver. The bundled non-preprint providers therefore treat `before` as audit context rather than a destructive retrieval filter; arXiv can safely filter on its v1 date.
