# Stale scene revision

When a mutation carries a revision older than the active scene, reject it with
`STALE_SCENE_REVISION`. Do not mutate or silently refresh the command.
