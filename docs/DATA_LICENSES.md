# Data and derived-artifact notices

NoveltyAudit source code and the installable Skill are licensed under Apache-2.0; see the repository `LICENSE`.

The external `eacl2026-assessing-paper-novelty` dataset (`tudatalib/4988`) is published by its maintainers under CC BY-NC 4.0. Its raw archive and extracted records are not redistributed in this repository.

`docs/bridge-base-rate-summary.json` is a derived aggregate measurement from that dataset. It contains counts, rates, interval estimates, the source dataset identifier, its license label, and the verified source-archive checksum—not the raw dataset. Users should consult the source dataset terms when reusing this derived artifact. This notice does not make a legal determination about which rights may attach to a particular aggregate use.

Source: [TUdatalib record 4988](https://tudatalib.ulb.tu-darmstadt.de/handle/tudatalib/4988).

## Public case studies

The root [`case-studies/`](../case-studies/README.md) directory contains three different evidence classes and does not flatten their licensing or epistemic status:

- The synthetic missing-killer case is project-authored and covered by the repository's Apache-2.0 license.
- The SafePatching reviewer-grounded case contains identifiers and project-authored paraphrases derived from TUdatalib case `09JVxsEZPf`. Dataset-derived fields remain subject to CC BY-NC 4.0 and are not relicensed by this repository. The case does not redistribute the annotation JSON, review text, or submission PDF.
- The RAG public case contains project-authored decomposition and bibliographic metadata. Linked papers remain under their source licenses; ACL Anthology and PMLR source pages state CC BY 4.0, while the case makes no redistribution-license claim for the linked NeurIPS target.

Under the [OpenReview Terms of Use](https://openreview.net/legal/terms), public comments and reviews are CC BY 4.0; an Article's own license is separately declared by the Article or venue. The case studies link the relevant forum but do not copy its reviews.
