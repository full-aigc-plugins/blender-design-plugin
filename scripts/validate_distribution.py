#!/usr/bin/env python3
"""Validate that the codex-blender plugin distribution conforms to the Codex plugin spec.

The rules implemented here mirror Codex's own manifest handling
(`codex-rs/plugin/src/plugin_id.rs`, `core-plugins/src/manifest.rs`,
`core-plugins/src/marketplace.rs`), not an invented schema:

  - `.codex-plugin/plugin.json` is a discovered manifest path
  - plugin `name` is a valid identifier segment: ASCII letters, digits, `.`, `_`, `-`;
    no leading/trailing dot and no `..`; not empty
  - `skills` is a string or list of strings, each starting with `./`, never `./`,
    containing no `..`, and staying inside the plugin root
  - every declared skills directory exists and contains `<skill>/SKILL.md` whose
    frontmatter `name` matches its directory name
  - `.agents/plugins/marketplace.json` has a valid `name` and a non-empty `plugins`
    array whose `name` matches the manifest name and whose `source` resolves
  - provenance, no oversized binaries, no symlinks, no secrets

A `LICENSE` file is deliberately NOT required (license selection is an open human
decision), and `license`/`repository`/`entryPoint` are NOT manifest fields.
"""

import json
import os
import re
import sys

_DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MANIFEST_REL = os.path.join(".codex-plugin", "plugin.json")
_MARKETPLACE_REL = os.path.join(".agents", "plugins", "marketplace.json")

_EXPECTED_SKILLS = [
    "codex-blender-use",
    "codex-blender-inspect",
    "codex-blender-export-preview",
    "codex-blender-link",
]

_MAX_BINARY_BYTES = 1024 * 1024  # 1 MiB

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

# Mirrors validate_plugin_segment() in codex-rs/plugin/src/plugin_id.rs
_SEGMENT_CHARS = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_segment(value, kind):
    """Return an error string, or None when the segment is valid."""
    if not value:
        return f"invalid {kind}: must not be empty"
    allow_dots = kind == "plugin name"
    if allow_dots and value in (".", ".."):
        return f"invalid {kind}: path traversal is not allowed"
    if allow_dots and (value.startswith(".") or value.endswith(".") or ".." in value):
        return f"invalid {kind}: dots must separate non-empty name segments"
    allowed = "ASCII letters, digits, `.`, `_`, and `-`" if allow_dots else "ASCII letters, digits, `_`, and `-`"
    if not _SEGMENT_CHARS.match(value):
        return f"invalid {kind}: only {allowed} are allowed"
    if not allow_dots and "." in value:
        return f"invalid {kind}: only {allowed} are allowed"
    return None


def validate_manifest_path(field, raw):
    """Mirror resolve_manifest_path(): return (resolved_rel, error)."""
    if not raw:
        return None, f"{field}: path must not be empty"
    if not raw.startswith("./"):
        return None, f"{field}: path must start with `./` relative to plugin root"
    relative = raw[2:]
    if not relative:
        return None, f"{field}: path must not be `./`"
    if any(component == ".." for component in relative.split("/")):
        return None, f"{field}: path must not contain '..'"
    if relative.startswith("/"):
        return None, f"{field}: path must stay within the plugin root"
    return relative, None


def _read_skill_frontmatter(path):
    """Return the frontmatter dict of a SKILL.md, or None if absent/malformed."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fields = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _is_binary(path):
    binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".webm", ".avi",
                   ".exe", ".dll", ".so", ".dylib", ".bin", ".zip", ".tar", ".gz",
                   ".woff", ".woff2", ".ttf", ".eot"}
    _, ext = os.path.splitext(path)
    return ext.lower() in binary_exts


def main(root: str | None = None) -> int:
    """Validate the distribution rooted at `root` (defaults to this repo)."""
    root = root or _DEFAULT_ROOT
    errors: list[str] = []

    # --- plugin manifest ---
    plugin_path = os.path.join(root, _MANIFEST_REL)
    if not os.path.isfile(plugin_path):
        print(f"ERROR: Missing {_MANIFEST_REL}")
        return 1
    with open(plugin_path, encoding="utf-8") as handle:
        try:
            plugin = json.load(handle)
        except json.JSONDecodeError as exc:
            print(f"ERROR: {_MANIFEST_REL} is not valid JSON: {exc}")
            return 1

    name = plugin.get("name", "")
    error = validate_segment(name, "plugin name")
    if error:
        errors.append(f"plugin.json name {name!r}: {error}")

    for field in ("version", "description"):
        if not plugin.get(field):
            errors.append(f"plugin.json missing required field: {field}")

    if "skills" not in plugin:
        errors.append("plugin.json missing required field: skills")
    else:
        declared = plugin["skills"]
        if isinstance(declared, str):
            declared = [declared]
        if not isinstance(declared, list) or not declared:
            errors.append("plugin.json skills must be a path string or a non-empty list")
            declared = []
        for raw in declared:
            relative, error = validate_manifest_path("skills", raw)
            if error:
                errors.append(error)
                continue
            skills_dir = os.path.join(root, relative)
            if not os.path.isdir(skills_dir):
                errors.append(f"skills directory does not exist: {raw}")
                continue
            for entry in sorted(os.listdir(skills_dir)):
                skill_md = os.path.join(skills_dir, entry, "SKILL.md")
                if not os.path.isfile(skill_md):
                    errors.append(f"skills/{entry} has no SKILL.md")
                    continue
                front = _read_skill_frontmatter(skill_md)
                if front is None:
                    errors.append(f"skills/{entry}/SKILL.md has no frontmatter block")
                    continue
                if not front.get("name"):
                    errors.append(f"skills/{entry}/SKILL.md frontmatter has no name")
                elif front["name"] != entry:
                    errors.append(
                        f"skills/{entry}/SKILL.md name {front['name']!r} does not match its directory"
                    )
                if not front.get("description"):
                    errors.append(f"skills/{entry}/SKILL.md frontmatter has no description")

    # --- interface.defaultPrompt documented limits (3 prompts, 128 chars each) ---
    prompts = (plugin.get("interface") or {}).get("defaultPrompt")
    if prompts is not None:
        if isinstance(prompts, str):
            prompts = [prompts]
        if not isinstance(prompts, list):
            errors.append("interface.defaultPrompt must be a string or a list of strings")
        else:
            if len(prompts) > 3:
                errors.append("interface.defaultPrompt supports at most 3 prompts")
            for prompt in prompts:
                if not isinstance(prompt, str) or len(prompt) > 128:
                    errors.append(
                        "interface.defaultPrompt entries must be strings of at most 128 characters"
                    )

    for skill_name in _EXPECTED_SKILLS:
        if not os.path.isfile(os.path.join(root, "skills", skill_name, "SKILL.md")):
            errors.append(f"Missing expected Skill: skills/{skill_name}/SKILL.md")

    # --- marketplace manifest ---
    marketplace_path = os.path.join(root, _MARKETPLACE_REL)
    if not os.path.isfile(marketplace_path):
        errors.append(f"Missing {_MARKETPLACE_REL}")
    else:
        with open(marketplace_path, encoding="utf-8") as handle:
            try:
                marketplace = json.load(handle)
            except json.JSONDecodeError as exc:
                errors.append(f"{_MARKETPLACE_REL} is not valid JSON: {exc}")
                marketplace = None
        if marketplace is not None:
            market_name = marketplace.get("name", "")
            error = validate_segment(market_name, "marketplace name")
            if error:
                errors.append(f"marketplace.json name {market_name!r}: {error}")
            plugins = marketplace.get("plugins")
            if not isinstance(plugins, list) or not plugins:
                errors.append("marketplace.json must declare a non-empty `plugins` array")
            else:
                for index, entry in enumerate(plugins):
                    if not isinstance(entry, dict):
                        errors.append(f"marketplace.json plugins[{index}] is not an object")
                        continue
                    entry_name = entry.get("name", "")
                    error = validate_segment(entry_name, "plugin name")
                    if error:
                        errors.append(f"marketplace.json plugins[{index}] name: {error}")
                    elif name and entry_name != name:
                        errors.append(
                            f"marketplace.json plugins[{index}] name {entry_name!r} "
                            f"does not match plugin.json name {name!r}"
                        )
                    source = entry.get("source")
                    if source is None:
                        errors.append(f"marketplace.json plugins[{index}] has no `source`")
                    elif isinstance(source, str):
                        if not source:
                            errors.append(f"marketplace.json plugins[{index}] source is empty")
                    elif isinstance(source, dict):
                        kind = source.get("source")
                        if kind == "local":
                            raw = source.get("path", "")
                            if raw not in (".", "./"):
                                _, error = validate_manifest_path(
                                    f"plugins[{index}].source.path", raw
                                )
                                if error:
                                    errors.append(error)
                                else:
                                    if not os.path.isdir(os.path.join(root, raw)):
                                        errors.append(
                                            f"plugins[{index}].source.path does not exist: {raw}"
                                        )
                        elif kind not in ("url", "git-subdir", "npm", "git"):
                            errors.append(
                                f"marketplace.json plugins[{index}] source kind {kind!r} "
                                "is not a supported kind"
                            )
                    else:
                        errors.append(
                            f"marketplace.json plugins[{index}] source has an unsupported shape"
                        )

    # --- schemas ---
    for schema_name in ("scene_receipt", "artifact_receipt"):
        schema_path = os.path.join(root, "schemas", f"{schema_name}.schema.json")
        if not os.path.isfile(schema_path):
            errors.append(f"Missing schema file: schemas/{schema_name}.schema.json")

    # --- vendored provenance ---
    upstream_path = os.path.join(root, "vendor", "jimeng_blender_uploader", "UPSTREAM.md")
    if not os.path.isfile(upstream_path):
        errors.append("Missing vendor/jimeng_blender_uploader/UPSTREAM.md (provenance record)")
    else:
        with open(upstream_path, encoding="utf-8") as handle:
            content = handle.read()
        for vendored in ("dcc_config.py", "upload_bridge.py", "settings.py", "variant.py",
                         "viewport_render.py", "operators.py", "panel.py", "state.py",
                         "__init__.py"):
            if vendored not in content:
                errors.append(f"UPSTREAM.md missing record for {vendored}")

    # --- no oversized binaries, no symlinks, no secrets ---
    for root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__", "node_modules")]
        for entry in files + dirs:
            path = os.path.join(root, entry)
            if os.path.islink(path):
                errors.append(f"Symlink found: {os.path.relpath(path, root)}")
        for entry in files:
            path = os.path.join(root, entry)
            if _is_binary(path) and os.path.getsize(path) > _MAX_BINARY_BYTES:
                errors.append(
                    f"Binary exceeds {_MAX_BINARY_BYTES} bytes: "
                    f"{os.path.relpath(path, root)} ({os.path.getsize(path)} bytes)"
                )
            if not entry.endswith((".py", ".json", ".md", ".txt", ".yml", ".yaml", ".js")):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
            except OSError:
                continue
            for pattern in _SECRET_PATTERNS:
                if pattern.search(content):
                    errors.append(
                        f"Possible secret in {os.path.relpath(path, root)}"
                    )

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1

    print("Distribution validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
