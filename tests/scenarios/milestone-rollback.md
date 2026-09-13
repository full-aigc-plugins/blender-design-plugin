# Milestone rollback

When any mutation in an active milestone fails, reopen its checkpoint, confirm the scene signature,
restore the begin revision, and do not replay the failed or later commands.
