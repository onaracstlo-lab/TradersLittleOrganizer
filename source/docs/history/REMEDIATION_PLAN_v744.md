# Build 744 / Process v170 remediation plan

Source baseline: Build 743. Process baseline: v169.
1. Distinguish local object-store write failure from line-ending warnings.
2. Prepare a clean source snapshot; move Git metadata to independently created user-local temporary storage, verify its location, stage the full tree, and retry only classified access/lock failures in fresh stores.
3. Confirm failure closes before commit or push, validate safe cleanup and no foreign metadata deletion; preserve repository-local commit identity and all prior signing, release immutability, hash and promotion controls.
4. Test real Git behavior, process regression and full application regression; update current documentation and references. Preserve immutable previous bundles and historical evidence.
5. Produce complete flat source and build-process archives with verified manifests. Native Windows staging/hosted CI, signing and installer acceptance are mandatory and remain pending.

Application code and masters otherwise unchanged from Build 743. See archive of its W1–W16 dispositions in docs/history/REMEDIATION_PLAN_v743.md.

## Execution

Local code, tests, documents and archive verification completed. See REGRESSION_RESULTS_v744.txt for observed results and limits. Native Windows staging and hosted acceptance remain pending.
