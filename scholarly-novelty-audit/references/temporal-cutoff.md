# Strict temporal cutoff

The adverse evidence date is the earliest date on which the work was publicly accessible, not the date most convenient to the verdict.

Prefer complete dates in this order of evidentiary value: preprint v1, first public OpenReview manuscript, accepted manuscript or publisher online-first, Crossref published-online or issued date, then proceedings date. Preserve every observed version date.

If only a year is known, mark `DATE_UNCERTAIN`. Never invent January 1. In strict mode, only `ELIGIBLE` papers may support a direct precedent, MPS, or historical bridge. Keep `POST_CUTOFF` and `DATE_UNCERTAIN` papers in clearly separated report sections.

When versions disagree, use the earliest verified public date and retain provenance for the conflicting values.

For arXiv full text, a bare `/pdf/<id>` URL is the current revision and is never sufficient for strict historical evidence. Record the exact version number and its verified `updated` date, resolve the complete version history when the current revision post-dates the cutoff, and acquire the greatest downloadable `vN` whose submission date is on or before the cutoff. The acquisition manifest must preserve the selected version, version date, cutoff, and selection method. If the version history is incomplete, inconsistent, or redirects away from the explicitly requested version, fail closed and do not fall back to the current PDF.

Push the cutoff into most ordinary provider queries where supported (`to_publication_date` for OpenAlex and `publicationDateOrYear` for Semantic Scholar) to reduce post-cutoff noise. Never rely on that prefilter for strict history: a journal version may appear after the cutoff while its preprint was public before it. `search-plan` therefore designates at least one query family as an unfiltered temporal-recall backstop and records that fact in every SearchRun. Citation-graph expansion always uses the same wider-retrieval rule because a hidden historical bridge can otherwise create false comfort. Merge versions and apply the deterministic earliest-public-date resolver downstream. arXiv cutoff-filtered pages preserve raw entry counts and advance by raw offsets, so a page containing only post-cutoff records cannot fake provider exhaustion.
