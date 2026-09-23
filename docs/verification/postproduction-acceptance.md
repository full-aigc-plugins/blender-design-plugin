# Post-Production Acceptance (Task 10)

## Commands Verified

| Command | Plan Name -> Blender Mapping | Dispatch Count |
|---------|------------------------------|---------------|
| `material.add_node` | Principled->ShaderNodeBsdfPrincipled, Image Texture->ShaderNodeTexImage, Normal Map->ShaderNodeNormalMap, Mapping->ShaderNodeMapping, Math->ShaderNodeMath, Mix->ShaderNodeMix, ColorRamp->ShaderNodeValToRGB | 11 |
| `material.connect_nodes` | (generic node tree links) | 2 |
| `sequence.split` | SCENE strip split | 1 |
| `sequence.configure_proxy` | authorized directory validation | 2 |
| `sequence.add_modifier` | Color Balance->COLOR_BALANCE, Brightness/Contrast->BRIGHT_CONTRAST, Hue Correct->HUE_CORRECT, Mask->MASK, White Balance->WHITE_BALANCE, Tonemap->TONEMAP, Curves->CURVES | 7 |
| `sequence.color_grade` | lift/gamma/gain on COLOR_BALANCE modifier | 2 |

## Whitelist Mapping (plan name -> real Blender 5.2.1 identifier)

### Shader Nodes (material.add_node)
| Plan Name | Blender bl_idname | Verified |
|-----------|-------------------|----------|
| Principled | ShaderNodeBsdfPrincipled | accepted |
| Image Texture | ShaderNodeTexImage | accepted |
| Normal Map | ShaderNodeNormalMap | accepted |
| Mapping | ShaderNodeMapping | accepted |
| Math | ShaderNodeMath | accepted |
| Mix | ShaderNodeMix | accepted |
| ColorRamp | ShaderNodeValToRGB | accepted |
| TotallyBogusNodeXYZ | (none) | rejected with INVALID_ARGUMENT |

### VSE Modifier Types (sequence.add_modifier)
| Plan Name | Blender Enum | Verified |
|-----------|-------------|----------|
| Color Balance | COLOR_BALANCE | accepted |
| Brightness/Contrast | BRIGHT_CONTRAST | accepted |
| Hue Correct | HUE_CORRECT | accepted |
| Mask | MASK | accepted |
| White Balance | WHITE_BALANCE | accepted |
| Tonemap | TONEMAP | accepted |
| Curves | CURVES | accepted |
| FakeModifierType99 | (none) | rejected with INVALID_ARGUMENT |

## Acceptance Evidence

- Proxy unauthorized: `/tmp/unauthorized_proxy_dir` rejected with `OUTPUT_NOT_AUTHORIZED`; no directory created
- VSE media: H.264/AAC, 24fps verified via probe_video(check_audio=True)
- 12fps framerate mutation: correctly fails on 12fps video
- PNG codec mutation: correctly fails on non-video file
- Reopen: material nodes (5), links (2), strips (5), proxy, modifiers all preserved
- Node rename mutation: comparison correctly breaks after renaming a node
- color_grade delta: 0.388 (non-trivial) vs 0.0 (identity) -- measured pixel L1
- connect_nodes delta: link count 1->2 (delta=1), removal mutation verified

## Maturity

All six commands reach L3 maturity with runtime evidence from `tests/runtime/postproduction_acceptance.py`.
