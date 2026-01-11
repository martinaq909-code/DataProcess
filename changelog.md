# 更新日志 (Changelog)

本项目的所有显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)，
并且本项目遵循 [语义化版本 (Semantic Versioning)](https://semver.org/spec/v2.0.0.html)。

## [v0.1.0] - 2025-12-29

### 新增 (Added)
- **道路矢量筛选功能**: 新增基于道路密度/覆盖率的瓦片筛选功能。
  - 新增 `core/road_coverage_analyzer.py` 模块，利用 `geopandas` 和 `shapely` 进行矢量分析。
  - 支持基于长度的比率计算（道路总长度 vs 瓦片对角线长度）。
  - 自动处理坐标系转换至 WGS84 (EPSG:4326)。
- **GUI 界面集成**: 更新了“数据预处理”选项卡中的“瓦片清洗”区块。
  - 添加了启用/禁用道路筛选的复选框。
  - 添加了用于选择道路矢量文件（Shapefile, GeoJSON）的文件浏览按钮。
  - 添加了阈值控制，用于精细调节筛选灵敏度。
- **命令行流程工具 (CLI)**: 创建了 `process_pipeline.py`，实现全自动化的命令行处理。
  - 自动执行完整 7 步流程：读取边界、下载瓦片、获取 OSM 数据、清洗 OSM 数据、拼接瓦片、黑边过滤和道路筛选。
- **说明文档**: 编写了 `README_PIPELINE.md`，包含 CLI 工具的详细使用指南。
- **测试套件**: 
  - 在 `tests/test_road_coverage_analyzer.py` 中编写了单元测试。
  - 创建了用于验证完整流水线的端到端验证脚本。

### 变更 (Changed)
- **TileFilter 增强**: 将道路覆盖率分析器集成到核心过滤逻辑中。
- **TileDownloader 更新**: 优化了错误处理和断点续传逻辑。
- **GUI 优化**: 提升了预处理界面的交互响应速度。

### 修复 (Fixed)
- **下载配置**: 修正了 Google 卫星影像的配置键名（由 `google_satellite` 改为 `google`）。
- **路径处理**: 修复了在 Windows 环境下跨平台路径解析的若干问题。

---
*由 Antigravity AI 生成*
