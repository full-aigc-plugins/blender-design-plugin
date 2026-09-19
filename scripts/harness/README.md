# Harness 保留边界

`scripts/harness/` 是 `blender-design-plugin` 既有 managed-mode、Connector 和历史验收
测试仍在引用的兼容副本，不是新功能的事实源。新的跨客户端能力只能先进入
`blender-mcp`，插件运行时通过 `runtime.lock.json` 消费其发行包。

本目录选择“持续差分门禁”而不是删除：`scripts/check_harness_drift.py` 同时校验本地
兼容树和锁定 Runtime 内上游树的规范化 SHA-256。任一侧变化都会失败；升级 Runtime
时必须先审查差异、运行受影响的 managed-mode 测试，再明确更新
`config/harness-boundary.json`。不得把未审查的上游覆盖或插件私有能力静默混入另一侧。

