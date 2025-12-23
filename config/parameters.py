"""项目参数配置模块 - 集中管理所有可配置的参数"""

# SLIC超像素分割参数
SLIC_CONFIG = {
    "n_segments": 1000,
    "compactness": 10.0,
    "max_num_iter": 15,
    "sigma": 1.0,
    "enforce_connectivity": True,
}

SLIC_PRESETS = {
    "standard": {"n_segments": 1000, "compactness": 10.0, "desc": "标准配置"},
    "road_precise": {"n_segments": 2000, "compactness": 1.0, "desc": "道路精细 (推荐)"},
    "coarse": {"n_segments": 500, "compactness": 5.0, "desc": "粗分割 (快速)"},
    "fine": {"n_segments": 5000, "compactness": 0.5, "desc": "超精细 (颜色复杂)"},
    "highway": {"n_segments": 1000, "compactness": 10.0, "desc": "高速公路 (规则)"},
}

# 道路缓冲区参数
ROAD_BUFFER_CONFIG = {
    "motorway": 30.0,
    "trunk": 30.0,
    "primary": 30.0,
    "secondary": 20.0,
    "tertiary": 15.0,
    "unclassified": 20.0,
    "residential": 12.0,
    "default": 8.0,
}

# 前景/背景点采样参数
SAMPLING_CONFIG = {
    "sample_interval_px": 50.0,
    "background_from_centroids": True,
}

SAMPLING_PRESETS = {
    "dense": {"sample_interval_px": 25.0, "desc": "密集采样"},
    "standard": {"sample_interval_px": 50.0, "desc": "标准采样 (推荐)"},
    "sparse": {"sample_interval_px": 75.0, "desc": "稀疏采样"},
}

# 瓦片拼接参数
TILE_CONFIG = {
    "tile_size": 256,
    "composite_size": 1024,
}

COMPOSITE_PRESETS = {
    "small": {"composite_size": 512, "desc": "小 (512×512)"},
    "standard": {"composite_size": 1024, "desc": "标准 (1024×1024)"},
    "large": {"composite_size": 2048, "desc": "大 (2048×2048)"},
}

# 瓦片下载参数
DOWNLOAD_CONFIG = {
    "max_workers": 4,
    "per_thread_min_sleep": 0.3,
    "per_thread_max_sleep": 1.2,
    "batch_size": 3000,
    "batch_pause_min": 60.0,
    "batch_pause_max": 180.0,
    "max_retries": 6,
    "backoff_factor": 1.5,
    "request_timeout": 10.0,
}

DOWNLOAD_PRESETS = {
    "conservative": {
        "max_workers": 2,
        "per_thread_min_sleep": 1.0,
        "per_thread_max_sleep": 2.0,
        "batch_pause_min": 120.0,
        "batch_pause_max": 240.0,
        "desc": "保守 (最安全)"
    },
    "standard": {
        "max_workers": 4,
        "per_thread_min_sleep": 0.3,
        "per_thread_max_sleep": 1.2,
        "batch_pause_min": 60.0,
        "batch_pause_max": 180.0,
        "desc": "标准 (推荐)"
    },
    "aggressive": {
        "max_workers": 6,
        "per_thread_min_sleep": 0.1,
        "per_thread_max_sleep": 0.5,
        "batch_pause_min": 30.0,
        "batch_pause_max": 60.0,
        "desc": "激进 (最快)"
    },
}


def get_slic_config(preset="standard"):
    """获取SLIC配置"""
    if preset not in SLIC_PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    config = SLIC_CONFIG.copy()
    preset_data = SLIC_PRESETS[preset]
    config.update({k: v for k, v in preset_data.items() if k != "desc"})
    return config


def get_sampling_config(preset="standard"):
    """获取采样配置"""
    if preset not in SAMPLING_PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    config = SAMPLING_CONFIG.copy()
    preset_data = SAMPLING_PRESETS[preset]
    config.update({k: v for k, v in preset_data.items() if k != "desc"})
    return config


def get_download_config(preset="standard"):
    """获取下载配置"""
    if preset not in DOWNLOAD_PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    config = DOWNLOAD_CONFIG.copy()
    preset_data = DOWNLOAD_PRESETS[preset]
    config.update({k: v for k, v in preset_data.items() if k != "desc"})
    return config


def print_all_presets():
    """打印所有可用的预设"""
    print("\n" + "="*70)
    print("AVAILABLE PRESETS")
    print("="*70)
    
    print("\nSLIC Presets:")
    for name, cfg in SLIC_PRESETS.items():
        print(f"  {name:20} - {cfg['desc']}")
        print(f"    n_segments={cfg['n_segments']}, compactness={cfg['compactness']}")
    
    print("\nSampling Presets:")
    for name, cfg in SAMPLING_PRESETS.items():
        print(f"  {name:20} - {cfg['desc']}")
        print(f"    interval={cfg['sample_interval_px']}px")
    
    print("\nDownload Presets:")
    for name, cfg in DOWNLOAD_PRESETS.items():
        print(f"  {name:20} - {cfg['desc']}")
        print(f"    workers={cfg['max_workers']}")
    
    print("\nComposite Presets:")
    for name, cfg in COMPOSITE_PRESETS.items():
        print(f"  {name:20} - {cfg['desc']}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print_all_presets()








