# Signing and additional platforms: remaining verification

The tested distributable is Windows x64. Signing and other platforms remain
open in issue #26; a source run is not a native packaged-app smoke test.

## Windows signing

An owner must choose a certificate/provider and supply signing credentials using
repository secrets. Cost and account ownership are owner decisions. No signing
credentials have been requested, purchased or embedded. When available, sign both
EXEs, timestamp signatures, verify them on a clean Windows host, then build the
archive/checksum. Never store private keys in the repository or portable ZIP.

## Linux prototype plan

Use a native Linux PyInstaller build of both entry points with common resource/data
rules, add an executable shell launcher or desktop entry, and test on a fresh host
with the intended glibc baseline. Include Tcl/Tk and image libraries. Verify file
permissions survive archive extraction, and run diagnostics under a real display
and Xvfb with Python removed from PATH. Review audio support (currently Windows-only).

## macOS prototype plan

Build on macOS for each claimed architecture, use an app bundle and companion CLI,
route writable data outside the signed app bundle, and test Tk assets and input.
Sign/notarize only after the owner supplies the required Apple account/credentials.
Verify Gatekeeper behavior on a clean host. Do not advertise universal support
from a build tested on only one architecture.

These are implementation plans, not completed portable packages. Public non-Windows
releases should wait for successful native builds and extracted-package checks.
