# Official Uploader Runtime Verification

**Date:** 2026-09-13  
**Blender:** 5.2.1 LTS  
**Status:** `BLOCKED_MISSING_OFFICIAL_ADDON`

## Probe

Blender was started read-only in background mode and its enabled add-on keys
were enumerated. `jimeng_blender_uploader` was not present. The standard
Blender user add-on directories likewise contained no module with that name.

The plugin was not installed, enabled, copied, or modified because the product
contract requires the user to obtain and enable the official package.

## Verified Without the Add-on

- missing add-on fails with `OFFICIAL_UPLOADER_NOT_AVAILABLE`;
- capability projection reports module/version/operator availability;
- camera render and existing-video routes invoke exactly one official operator;
- status output excludes the loopback token and `thirdparty_id`;
- stale links cannot be opened;
- opening a current link is a separately gated command;
- completion is `JimengLinkReady`, never Seedance `Completed`.

## Unblock

The user must install and enable the official `jimeng_blender_uploader` package
inside Blender. A later authorized Connector smoke test can then exercise
`official_uploader.inspect`, one handoff operation, status, and optional open.
