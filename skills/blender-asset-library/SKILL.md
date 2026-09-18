---
name: blender-asset-library
description: 从 PolyHaven 等 CC0 资产库为 Blender 场景取材：搜索资产、按体积纪律经 asset.fetch_url 下载、应用 HDRI 环境与 PBR 材质；用户要 HDRI、环境贴图、贴图材质、低模道具或提到 PolyHaven 时使用。
license: Apache-2.0
---

# Blender 资产库（PolyHaven 优先）

## 快速开始

1. “给场景配一个日落 HDRI。”→ 搜索 `hdri` + `sunset`，选 2K，`asset.fetch_url` 下载后应用到世界环境。
2. “这个模型缺木纹贴图。”→ 搜 `textures` + `wood`，下载 1K 贴图集，按 PBR 接线表接到 Principled BSDF。
3. “找个低模椅子摆进场景。”→ 搜 `models` + `chair`，下载 glb 后用 `asset.import_file` 导入并落地。

面向使用 Blender 插件连接真实 Blender 会话的用户。资产来自 PolyHaven（CC0：免费、可商用、无需署名）。

## 体积纪律（硬规则，先于一切下载）

1. HDRI 默认 2K；纹理默认 1K；模型优先 glTF 低模。4K/8K 仅在用户明确要求时使用。
2. 下载前必须从 `asset.fetch_url` 的结果或 API 元数据报出预计大小；超过 50MB 需用户确认。
3. 禁止批量囤积：一次任务只下载当前场景需要的资产；提醒用户缓存位于
   `polyhaven/` 资产根目录，可整目录删除释放空间。
4. 每次只下载一个变体；不要为对比下载多份分辨率。

## 执行路径（按环境分流）

1. **标准路径**：用闭合命令 `asset.fetch_url`（url 必填，filename 可选）。域名白名单：
   `https://api.polyhaven.com`（搜索元数据）与 `https://dl.polyhaven.org`（资产文件）。
   下载落入已授权资产根的 `polyhaven/` 子目录，随后即可被
   `asset.import_file`（模型）与材质/世界环境命令直接使用。
2. **搜索用法**：`GET https://api.polyhaven.com/assets?t=hdri`（type 可为
   hdri/textures/models）按关键词过滤返回的 JSON；`GET
   https://api.polyhaven.com/files/<id>` 返回各分辨率下载地址，**优先选 1K/2K**
   条目交给 `asset.fetch_url`。
3. 若宿主另有 BlenderMCP 类 MCP 工具提供 polyhaven 工具，优先用那些工具；本技能
   的体积纪律仍然适用。

## 应用配方

- **HDRI → 世界环境**：世界节点树放入 Environment Texture 节点，坐标用
  Generated，强度默认 1.0；影棚产品图选 `studio_small_*` 系，户外场景按时间氛围选。
- **PBR 贴图集 → Principled BSDF**：`*_diffuse`（或 albedo）接 Base Color，
  `*_nor_*` 经 Normal Map 节点接 Normal，`*_rough_*` 接 Roughness，
  `*_disp` 经 Displacement 接输出；非色彩数据贴图记得把颜色空间设为 Non-Color。
- **模型 → 导入落地**：`asset.import_file` 之后统一缩放、贴地、检查包围盒，
  与 `blender-asset-workflow` 的接管流程一致。

## 版权与边界

- PolyHaven 全库 CC0：免费、可商用、无需署名；不要为 PolyHaven 资产添加署名节点。
- 若后续接入 Poly Pizza（CC-BY）等需署名库，必须把署名写入对象的 custom
  property 并随交付说明输出。
- `asset.fetch_url` 只允许白名单域名与白名单后缀（.hdr/.exr/.glb/.gltf/.png/.jpg），
  单文件 200MB 硬上限；不要尝试绕过，也不要建议用户手动下载超大体积。

## 故障与边界

- `ASSET_NOT_AUTHORIZED`：资产根未获用户批准或域名不在白名单；向用户说明后停止。
- `DOWNLOAD_FAILED`：网络不可达或 CDN 异常；建议用户稍后重试或手动下载后走
  `asset.import_file`。
- 下载成功但导入失败：文件可能损坏，删除缓存副本后重新 `asset.fetch_url`。

## 按需参考

- 既有场景接管与落地细节见 `blender-asset-workflow` 的接管合同。
- 导出交付（GLB/FBX/USD）见 `blender-delivery-workflow`。
