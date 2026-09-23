# Project Portability Acceptance

**Task 11 -- Phase C: project packaging, dependency scanning, portability validation**

## Commands

| Command | Risk | Maturity | Evidence |
|---------|------|----------|----------|
| `asset.dependencies` | read | L3 | `tests/runtime/project_portability_acceptance.py` |
| `asset.validate_portability` | read | L3 | `tests/runtime/project_portability_acceptance.py` |
| `asset.package_project` | standard | L3 | `tests/runtime/project_portability_acceptance.py` |

## Dispatch counts

| Command | Count |
|---------|-------|
| `asset.dependencies` | 2 |
| `asset.package_project` | 3 |
| `asset.validate_portability` | 1 |
| **Total** | **6** |

## Acceptance criteria

### 1. Fresh directory succeeds; existing directory refused

- `asset.validate_portability` to a non-existent directory: `passed=True`
- `asset.package_project` to the same directory (now exists): raises `OUTPUT_NOT_AUTHORIZED` with message "target directory already exists"
- Demonstrated: both directions (fresh -> success, existing -> refusal)

### 2. Symlink and path escape refusals

- Symlink (`textures/symlink_tex.png` -> `textures/extra.png`): raises `ASSET_NOT_AUTHORIZED` "must not be a symlink"
- Path escape (`textures/../../outside/stolen.png`): raises `ASSET_NOT_AUTHORIZED` "is outside approved roots"
- Legitimate in-project file (`textures/extra.png`): accepted

### 3. Package reopens when original is unavailable

- Original `.blend` renamed before `open_mainfile` -- confirmed gone
- Packaged `.blend` reopened successfully
- All image paths resolve to locations **inside** the package directory

### 4. SHA-256 integrity

- Every packaged file has a SHA-256 recorded in the receipt
- Independent recomputation (hashlib) matches all recorded values
- Tampering one byte of a packaged file produces a different hash

### 5. License provenance

- `textures/diffuse.png` (no LICENSE file nearby): license = "unknown" (not silently dropped)
- `fonts/myfont.ttf` (LICENSE file present): license = "SIL Open Font License 1.1"

### 6. Project unchanged after packaging

- Snapshot of project directory files and mtimes before and after packaging: identical

## Dependency kinds observed

| Kind | Count | Real files |
|------|-------|------------|
| IMAGE | 1 | diffuse.png |
| FONT | 1 | myfont.ttf |
| AUDIO | 1 | tone.wav |
| EXTENSION | 1 | builtins |

## Runtime environment

- Blender 5.2.1 LTS, macOS arm64, background mode
- Acceptance script: `tests/runtime/project_portability_acceptance.py`
