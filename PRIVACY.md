# Privacy

Codex Blender is a local Codex plugin. It does not include telemetry, advertising, or a hosted
data service of its own.

## Local processing

Inspection, rendering, and encoding run entirely on the user's machine inside a locally invoked
Blender process that the user installed. Outputs, receipts, and logs are written only under paths
the user selected, within the approved output directory.

## Network activity (disclosed)

Two network behaviours exist and are disclosed here as this document requires:

1. **Protocol configuration fetch.** The vendored add-on fetches its video protocol limits from
   `https://jimeng.jianying.com/mweb/v1/get_dcc_protocol_config` before a render or an upload.
   The request carries no user project data; it is a configuration lookup. If it fails, the
   add-on falls back to built-in defaults and the export still proceeds.
2. **Loopback bridge.** To hand a rendered preview to the Jimeng web app, a local HTTP server is
   started bound to `127.0.0.1` on an ephemeral port, guarded by a random token. It serves the
   preview video and its prompt to the browser session that opens the returned link, and shuts
   down on a timer (30 minutes, or 60 seconds after the first download). It is not reachable from
   outside the machine.

No credentials are stored in this repository, and no project file is uploaded by this plugin
itself. Opening the returned Jimeng link is what transfers the video to the Jimeng web app, and
that transfer is governed by Jimeng's own terms.

Users should review third-party product privacy terms before enabling integrations.
