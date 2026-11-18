# TLO Build 677 — Platform test ownership

Source: GitHub Actions run 44123997856 (Build 675). The 71 failing cases are documented individually in `WINDOWS_TEST_REMEDIATION_v677.csv`. Build 677 corrects portable fixtures and runs intrinsically POSIX-only shell, mount, WSL, XDG Trash, `os.nice`, and FFmpeg Bash simulations on Linux; Win32 GUI, NTFS, CMD, MSI, PowerShell, volume, UNC, updater and destructive-path safety checks remain active on native Windows.

## Guardrails

- POSIX-only tests are marked at individual function or parameter level, **never** by excluding an entire test directory. They remain required in the Linux CI job.
- Windows-specific file paths are tested with native-drive and UNC fixtures. Windows-native tests are **not skipped** to hide failures.
- Plain Tk lacks TkDND; initialization should not crash, but the Win32 application's `TkinterDnD.Tk` must still handle real drag/drop in native acceptance.
- Case-only renames are checked by enumerating directory-entry spelling, since a case-insensitive lookup can resolve both old and new spellings.
- Byte-exact setlist tests use binary fixtures rather than platform-dependent newline translation.
- FFmpeg MSYS2 packaging remains a mandatory native Windows build gate. Bash-driven synthetic simulations remain mandatory on Linux.
- Generated deletion scripts must reject the root, `TLOHome` and its subtree, wrong or unverifiable volume labels, and untrusted symlinks.

## Evidence

Local Linux regression is a prerequisite, not an attestation of Windows CI. All matrix entries retain status **pending Windows hosted CI** until a new Build 677 GitHub Actions run has completed successfully. Zero native Windows failures and signed-release verification are required before promotion.
