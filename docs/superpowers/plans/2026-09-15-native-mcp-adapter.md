# Native MCP Adapter Implementation Plan

1. Add failing contract tests for manifest wiring, MCP lifecycle, registry-to-tool completeness,
   descriptor safety, forwarding, and onboarding assets.
2. Implement a dependency-free stdio JSON-RPC adapter and thin executable entry point.
3. Add `.mcp.json`, update distribution validation, and keep installed-relative paths portable.
4. Rename the trusted Connector UI action to `Start MCP Server` without changing its Harness runtime.
5. Add first-use Skill behavior and illustrated Chinese/English onboarding documentation.
6. Run focused tests, full tests, distribution validation, Skill validation, Connector packaging, and
   a live read-only MCP-to-Harness smoke in Blender.

This plan does not install the community `blender-mcp`, change user MCP configuration, submit external
work, or publish a release.
