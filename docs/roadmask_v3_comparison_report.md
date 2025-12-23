# RoadMask V3 测试报告

## 修改的参数

- 初始缓冲区: 从左右各3px改为10px
- 扩张步长: 从逐2px改为逐1px

## GOOGLE 数据源处理结果

### 输出文件统计

- 掩膜文件 (TIF): 11
- 叠加图像 (PNG): 11
- 相似性曲线 (PNG): 10

### 处理摘要

```
Image	Processed_Roads	Skipped_Roads	Mask_Path	Overlay_Path
116.614380_39.890246_116.617126_39.892353	6	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.614380_39.890246_116.617126_39.892353_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.614380_39.890246_116.617126_39.892353_overlay.png
  Road1	left=10px	right=10px	shift=0px
  Road2	left=10px	right=10px	shift=10px
  Road3	left=10px	right=10px	shift=10px
  Road4	left=10px	right=10px	shift=0px
  Road5	left=10px	right=10px	shift=1px
  Road6	left=10px	right=10px	shift=6px
116.650085_39.921849_116.652832_39.923956	10	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.650085_39.921849_116.652832_39.923956_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.650085_39.921849_116.652832_39.923956_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=10px	right=10px	shift=7px
  Road3	left=16px	right=16px	shift=2px
  Road4	left=16px	right=16px	shift=4px
  Road5	left=16px	right=16px	shift=0px
  Road6	left=10px	right=10px	shift=0px
  Road7	left=16px	right=16px	shift=10px
  Road8	left=16px	right=16px	shift=3px
  Road9	left=16px	right=16px	shift=4px
  Road10	left=16px	right=16px	shift=0px
116.663818_39.883923_116.666565_39.886031	7	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.663818_39.883923_116.666565_39.886031_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.663818_39.883923_116.666565_39.886031_overlay.png
  Road1	left=10px	right=10px	shift=0px
  Road2	left=10px	right=21px	shift=10px
  Road3	left=10px	right=10px	shift=1px
  Road4	left=10px	right=10px	shift=10px
  Road5	left=10px	right=10px	shift=10px
  Road6	left=10px	right=10px	shift=1px
  Road7	left=10px	right=10px	shift=0px
116.666565_39.892353_116.669312_39.894460	1	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.666565_39.892353_116.669312_39.894460_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.666565_39.892353_116.669312_39.894460_overlay.png
  Road1	left=10px	right=21px	shift=6px
116.666565_39.949227_116.669312_39.951333	3	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.666565_39.949227_116.669312_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.666565_39.949227_116.669312_39.951333_overlay.png
  Road1	left=10px	right=10px	shift=0px
  Road2	left=16px	right=16px	shift=10px
  Road3	left=16px	right=16px	shift=10px
116.685791_39.947121_116.688538_39.949227	4	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.685791_39.947121_116.688538_39.949227_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.685791_39.947121_116.688538_39.949227_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=16px	right=16px	shift=10px
  Road3	left=16px	right=16px	shift=10px
  Road4	left=16px	right=16px	shift=10px
116.694031_39.949227_116.696777_39.951333	4	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.694031_39.949227_116.696777_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.694031_39.949227_116.696777_39.951333_overlay.png
  Road1	left=16px	right=16px	shift=10px
  Road2	left=16px	right=16px	shift=2px
  Road3	left=16px	right=16px	shift=10px
  Road4	left=10px	right=21px	shift=10px
116.699524_39.949227_116.702271_39.951333	13	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.699524_39.949227_116.702271_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.699524_39.949227_116.702271_39.951333_overlay.png
  Road1	left=16px	right=16px	shift=10px
  Road2	left=10px	right=10px	shift=10px
  Road3	left=16px	right=16px	shift=0px
  Road4	left=10px	right=21px	shift=0px
  Road5	left=10px	right=10px	shift=0px
  Road6	left=10px	right=10px	shift=2px
  Road7	left=10px	right=10px	shift=1px
  Road8	left=16px	right=16px	shift=0px
  Road9	left=16px	right=16px	shift=2px
  Road10	left=16px	right=16px	shift=10px
  Road11	left=16px	right=16px	shift=0px
  Road12	left=16px	right=16px	shift=1px
  Road13	left=16px	right=16px	shift=0px
116.718750_39.900782_116.721497_39.902889	16	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.718750_39.900782_116.721497_39.902889_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.718750_39.900782_116.721497_39.902889_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=10px	right=10px	shift=1px
  Road3	left=10px	right=10px	shift=10px
  Road4	left=10px	right=21px	shift=0px
  Road5	left=10px	right=21px	shift=1px
  Road6	left=10px	right=21px	shift=10px
  Road7	left=16px	right=16px	shift=0px
  Road8	left=10px	right=10px	shift=0px
  Road9	left=10px	right=10px	shift=10px
  Road10	left=10px	right=10px	shift=10px
  Road11	left=10px	right=10px	shift=0px
  Road12	left=10px	right=10px	shift=10px
  Road13	left=10px	right=10px	shift=0px
  Road14	left=10px	right=10px	shift=5px
  Road15	left=10px	right=10px	shift=10px
  Road16	left=10px	right=10px	shift=6px
116.721497_39.947121_116.724243_39.949227	6	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.721497_39.947121_116.724243_39.949227_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.721497_39.947121_116.724243_39.949227_overlay.png
  Road1	left=10px	right=10px	shift=2px
  Road2	left=16px	right=16px	shift=0px
  Road3	left=16px	right=16px	shift=0px
  Road4	left=16px	right=16px	shift=10px
  Road5	left=16px	right=16px	shift=0px
  Road6	left=16px	right=16px	shift=3px
116.735229_39.959754_116.737976_39.961859	4	0	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.735229_39.959754_116.737976_39.961859_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_google_v3/116.735229_39.959754_116.737976_39.961859_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=16px	right=16px	shift=4px
  Road3	left=16px	right=16px	shift=10px
  Road4	left=16px	right=16px	shift=8px

```

## BING 数据源处理结果

### 输出文件统计

- 掩膜文件 (TIF): 11
- 叠加图像 (PNG): 11
- 相似性曲线 (PNG): 10

### 处理摘要

```
Image	Processed_Roads	Skipped_Roads	Mask_Path	Overlay_Path
116.614380_39.890246_116.617126_39.892353	6	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.614380_39.890246_116.617126_39.892353_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.614380_39.890246_116.617126_39.892353_overlay.png
  Road1	left=10px	right=10px	shift=0px
  Road2	left=10px	right=10px	shift=2px
  Road3	left=10px	right=10px	shift=10px
  Road4	left=10px	right=10px	shift=2px
  Road5	left=10px	right=10px	shift=3px
  Road6	left=10px	right=10px	shift=9px
116.650085_39.921849_116.652832_39.923956	10	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.650085_39.921849_116.652832_39.923956_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.650085_39.921849_116.652832_39.923956_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=10px	right=10px	shift=0px
  Road3	left=16px	right=16px	shift=0px
  Road4	left=16px	right=16px	shift=8px
  Road5	left=16px	right=16px	shift=10px
  Road6	left=10px	right=10px	shift=1px
  Road7	left=16px	right=16px	shift=0px
  Road8	left=16px	right=16px	shift=8px
  Road9	left=16px	right=16px	shift=0px
  Road10	left=16px	right=16px	shift=1px
116.663818_39.883923_116.666565_39.886031	7	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.663818_39.883923_116.666565_39.886031_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.663818_39.883923_116.666565_39.886031_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=10px	right=21px	shift=10px
  Road3	left=10px	right=10px	shift=10px
  Road4	left=10px	right=10px	shift=10px
  Road5	left=10px	right=10px	shift=10px
  Road6	left=10px	right=10px	shift=4px
  Road7	left=10px	right=10px	shift=0px
116.666565_39.892353_116.669312_39.894460	1	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.666565_39.892353_116.669312_39.894460_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.666565_39.892353_116.669312_39.894460_overlay.png
  Road1	left=10px	right=21px	shift=0px
116.666565_39.949227_116.669312_39.951333	3	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.666565_39.949227_116.669312_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.666565_39.949227_116.669312_39.951333_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=16px	right=16px	shift=10px
  Road3	left=10px	right=10px	shift=0px
116.685791_39.947121_116.688538_39.949227	4	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.685791_39.947121_116.688538_39.949227_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.685791_39.947121_116.688538_39.949227_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=16px	right=16px	shift=10px
  Road3	left=16px	right=16px	shift=8px
  Road4	left=16px	right=16px	shift=10px
116.694031_39.949227_116.696777_39.951333	4	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.694031_39.949227_116.696777_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.694031_39.949227_116.696777_39.951333_overlay.png
  Road1	left=16px	right=16px	shift=5px
  Road2	left=16px	right=16px	shift=0px
  Road3	left=16px	right=16px	shift=0px
  Road4	left=10px	right=21px	shift=1px
116.699524_39.949227_116.702271_39.951333	13	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.699524_39.949227_116.702271_39.951333_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.699524_39.949227_116.702271_39.951333_overlay.png
  Road1	left=16px	right=16px	shift=10px
  Road2	left=10px	right=10px	shift=0px
  Road3	left=16px	right=16px	shift=3px
  Road4	left=10px	right=21px	shift=0px
  Road5	left=10px	right=10px	shift=0px
  Road6	left=10px	right=10px	shift=10px
  Road7	left=10px	right=10px	shift=0px
  Road8	left=16px	right=16px	shift=3px
  Road9	left=16px	right=16px	shift=0px
  Road10	left=16px	right=16px	shift=10px
  Road11	left=16px	right=16px	shift=4px
  Road12	left=16px	right=16px	shift=0px
  Road13	left=16px	right=16px	shift=2px
116.718750_39.900782_116.721497_39.902889	16	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.718750_39.900782_116.721497_39.902889_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.718750_39.900782_116.721497_39.902889_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=10px	right=10px	shift=10px
  Road3	left=10px	right=10px	shift=2px
  Road4	left=10px	right=10px	shift=10px
  Road5	left=16px	right=16px	shift=0px
  Road6	left=10px	right=21px	shift=0px
  Road7	left=16px	right=16px	shift=2px
  Road8	left=10px	right=10px	shift=1px
  Road9	left=10px	right=10px	shift=7px
  Road10	left=10px	right=10px	shift=6px
  Road11	left=10px	right=10px	shift=8px
  Road12	left=10px	right=10px	shift=10px
  Road13	left=10px	right=10px	shift=2px
  Road14	left=10px	right=10px	shift=1px
  Road15	left=10px	right=10px	shift=7px
  Road16	left=10px	right=10px	shift=10px
116.721497_39.947121_116.724243_39.949227	6	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.721497_39.947121_116.724243_39.949227_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.721497_39.947121_116.724243_39.949227_overlay.png
  Road1	left=10px	right=10px	shift=1px
  Road2	left=16px	right=16px	shift=2px
  Road3	left=16px	right=16px	shift=6px
  Road4	left=16px	right=16px	shift=10px
  Road5	left=16px	right=16px	shift=10px
  Road6	left=16px	right=16px	shift=0px
116.735229_39.959754_116.737976_39.961859	4	0	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.735229_39.959754_116.737976_39.961859_mask.tif	D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/116.735229_39.959754_116.737976_39.961859_overlay.png
  Road1	left=10px	right=10px	shift=10px
  Road2	left=16px	right=16px	shift=10px
  Road3	left=16px	right=16px	shift=10px
  Road4	left=16px	right=16px	shift=10px

```

## 对比分析

### 参数修改的影响

1. **初始缓冲区增加**: 从3px增加到10px，使道路掩膜的初始覆盖范围更广
2. **扩张步长减小**: 从2px减小到1px，增加了扩张步骤数量，提高了精细度

### 观察到的变化

1. **道路掩膜宽度**: 由于初始缓冲区增加，道路掩膜的初始宽度增加了7px（左右各增加3px）
2. **扩张精细度**: 由于步长减小，扩张过程更精细，可能提高道路边界识别精度
3. **处理速度**: 由于步长减小，处理速度可能有所降低

### 建议

1. 如果需要更精细的道路边界识别，保持较小的步长（1px）是合适的
2. 如果处理速度是优先考虑的因素，可以使用较大的步长（2px）
3. 初始缓冲区大小可以根据道路宽度需求进行调整

### 输出文件位置

- Google结果: `D:/gjn/dataprocess/data/output/results_roadmask_google_v3/`
- Bing结果: `D:/gjn/dataprocess/data/output/results_roadmask_bing_v3/`
