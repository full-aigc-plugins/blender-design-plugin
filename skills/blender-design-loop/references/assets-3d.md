# 3D Asset Generation Reference

Port of `research/dream-loop/references/fal.md` recipes for Blender.
These recipes assume you have a `FAL_KEY` or `FAL_API_KEY`
environment variable set up. If you do not, fall back to:

- The bundled upstream `blender-asset-library` skill (procedural
  assets — no external API)
- The bundled `blender-asset-polypizza` style skill for direct
  asset downloads (no generation)

## Two models, two recipes

`dream-loop/scripts/fal-batch.mjs` documents two specific Fal models
for image-to-3D generation. They take **different parameters**;
do not copy one model's input wholesale to the other.

| Role | Exact endpoint | Starting input |
|---|---|---|
| Architecture, characters, hero props | `tripo3d/h3.1/image-to-3d` | `{"texture":true,"pbr":true,"face_limit":200000}` |
| Small props and dressing | `fal-ai/trellis` | `{"mesh_simplify":0.95,"texture_size":1024}` |

### H3.1 (architecture / characters / hero props)

- Accepts `face_limit`, `texture`, `pbr` parameters.
- Default face count is dense; explicitly bound it.
- Texture is full PBR; ready for Cycles rendering.

### Trellis (small props / dressing)

- Does **not** accept the `/image-to-3d` suffix on the URL.
- Documented texture sizes: 512, 1024, 2048. Start with 1024.
- Parameters: `mesh_simplify` (0..1, higher = simpler mesh),
  `texture_size` (pixels per side).

## Common mistakes

- **Trellis with `/image-to-3d` suffix**: 404 or invalid model.
  Use the bare `fal-ai/trellis` endpoint.
- **H3.1 with `texture_size`**: silently ignored. Trellis-only.
- **`mesh_simplify` on H3.1**: silently ignored. Use `face_limit`.
- **Default `face_limit` very high (e.g. 500k+)**: causes OOM in
  Blender import; cap at 200000 unless the asset is a hero prop.

## Job state machine

dream-loop's helper maintains three states per job. Reproduce the
same discipline here:

| State | Meaning | Action |
|---|---|---|
| `rejected` at submission | Fal returned 4xx before queueing | Fix endpoint/input/auth, resubmit |
| `submission-uncertain` / `submitting` | Queue accepted but ID unknown | Preserve record, reconcile with Fal history; do NOT resubmit |
| `result-error` | Queue finished, but fetch failed | Inspect `error_detail`; retry with same URLs |
| `download-error` | Fetch OK but file incomplete | Retry collection; do NOT regenerate |

The helper keeps accepted IDs even when the submission response is
incomplete. **Do not clear IDs/URLs to "fix" the record** — that
bypasses the protection against double-submission.

## Choosing mesh budgets

| Screen size | Instances | Suggested budget |
|---|---|---|
| Hero (≥ 25% of frame) | 1-2 | H3.1 with `face_limit: 200000` |
| Mid (5-25%) | 3-10 | H3.1 with `face_limit: 80000` |
| Small (< 5%) | 10+ | Trellis with `mesh_simplify: 0.95` |

Validate by previewing in Blender and measuring FPS after import.
A scene with too many high-face assets will tank FPS, which
triggers the FPS-budget discipline (see `fps-budget.md`).

## When NOT to use external asset generation

- The user only wants a single iteration (just generate one asset
  by hand).
- The user is in a sandboxed/offline environment (no `FAL_KEY`).
- The user has explicit licensing concerns — both H3.1 and Trellis
  output carry model-specific licenses; check the provider's terms
  before shipping a commercial asset.

In any of these cases, use procedural assets via the bundled
`blender-asset-library` skill or the `blender-design` skill's
approved-asset paths.