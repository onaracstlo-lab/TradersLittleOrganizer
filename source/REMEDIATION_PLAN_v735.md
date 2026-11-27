# Build 735 remediation and acceptance

| Item | Local status | Remaining acceptance |
|---|---|---|
| PowerShell HOME collision in MSI smoke test | Corrected | Native Windows test |
| Same collision in Windows diagnosis utility | Corrected | PowerShell runtime execution |
| Installer signing and database/shortcut checks | Retained | Signed native MSI installation/uninstallation |
| Documentation, archive and version consistency | Updated | Source hygiene and release-readiness |
| Hosted CI and signing | Pending | Existing v169 gates |

See REGRESSION_RESULTS_v735.txt for exact local results. The companion build process did not change.
