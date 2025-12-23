"""OSM data download utilities."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from tqdm import tqdm

from config.settings import DEFAULT_OSM_CONFIG, OSM_DATA_TYPES, OUTPUT_FORMATS

logger = logging.getLogger(__name__)

BBox = Tuple[float, float, float, float]


def bbox_chunks(bbox: BBox, max_size_deg: float = 0.5) -> Iterable[BBox]:
    """Split a bounding box into smaller tiles."""
    left, bottom, right, top = bbox
    lon_steps = int(max((right - left) / max_size_deg, 0)) + 1
    lat_steps = int(max((top - bottom) / max_size_deg, 0)) + 1

    for i in range(lon_steps):
        for j in range(lat_steps):
            l = left + i * max_size_deg
            r = min(l + max_size_deg, right)
            b = bottom + j * max_size_deg
            t = min(b + max_size_deg, top)
            yield (l, b, r, t)


def _validate_data_types(data_types: Optional[Sequence[str]]) -> List[str]:
    """Validate and normalise the requested data types."""
    if not data_types:
        return list(DEFAULT_OSM_CONFIG.get("data_types", ["road"]))

    normalized: List[str] = []
    for dt in data_types:
        key = dt.lower().strip()
        if key not in OSM_DATA_TYPES:
            raise ValueError(f"Unknown OSM data type: {dt}")
        if key not in normalized:
            normalized.append(key)
    return normalized


def _parse_bbox_input(bbox: Union[str, Sequence[float]]) -> BBox:
    """Parse bbox input from string or sequence."""
    if isinstance(bbox, str):
        parts = bbox.replace(";", ",").split(",")
    else:
        parts = list(bbox)

    if len(parts) != 4:
        raise ValueError("bbox must contain four numbers: left,bottom,right,top")

    try:
        left, bottom, right, top = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError("bbox contains invalid numeric values") from exc

    if not (left < right and bottom < top):
        raise ValueError("bbox values must satisfy left < right and bottom < top")

    return left, bottom, right, top


def _prepare_bounds_from_vector(
    vector_path: Union[str, Path],
    input_crs: Optional[str] = None,
) -> Tuple[BBox, Optional[BaseGeometry]]:
    """Compute bounds from a vector file and ensure WGS84 coordinates."""
    gdf = gpd.read_file(vector_path)
    if gdf.empty:
        raise ValueError(f"Input vector file is empty: {vector_path}")

    if gdf.crs is None:
        if not input_crs:
            raise ValueError("Input vector has no CRS; please specify input_crs")
        gdf = gdf.set_crs(input_crs)

    if gdf.crs.to_string().upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    union_geom = unary_union(gdf.geometry)
    if union_geom.is_empty:
        raise ValueError("Input vector does not provide a valid area")

    bounds = union_geom.bounds
    geom_types = {geom.geom_type for geom in gdf.geometry if geom is not None}
    polygonal_types = {"Polygon", "MultiPolygon"}
    clip_geometry: Optional[BaseGeometry] = union_geom if geom_types & polygonal_types else None

    return bounds, clip_geometry


def _infer_driver(output_path: Union[str, Path]) -> str:
    suffix = Path(output_path).suffix.lower().lstrip(".")
    return OUTPUT_FORMATS.get(suffix, "GeoJSON")


def _fetch_osm_for_bbox(
    bboxes: Iterable[BBox],
    data_types: Sequence[str],
    cache_dir: Union[str, Path],
    delay: float = 1.0,
) -> List[gpd.GeoDataFrame]:
    """Fetch OSM data for one or more bounding boxes."""
    results: List[gpd.GeoDataFrame] = []
    cache_dir = Path(cache_dir)

    bboxes_list = list(bboxes)
    total_bboxes = len(bboxes_list)
    logger.info(f"开始处理 {total_bboxes} 个 BBox 块")

    for bbox_idx, bbox in enumerate(bboxes_list, 1):
        left, bottom, right, top = bbox
        logger.info(f"  [{bbox_idx}/{total_bboxes}] 正在处理 BBox: ({left:.4f}, {bottom:.4f}, {right:.4f}, {top:.4f})")

        for dt_idx, data_type in enumerate(data_types, 1):
            logger.info(f"    → 数据类型 [{dt_idx}/{len(data_types)}]: {data_type}")
            config = OSM_DATA_TYPES[data_type]
            tags = config["tags"]
            primary_tag = config.get("primary_tag") or next(iter(tags.keys()))

            cache_key = f"{data_type}_{left:.6f}_{bottom:.6f}_{right:.6f}_{top:.6f}".replace(".", "_")
            cache_file = cache_dir / f"{cache_key}.geojson"

            if cache_file.exists() and cache_file.stat().st_size > 0:
                gdf = gpd.read_file(cache_file)
                if gdf.empty:
                    continue
                if "osm_data_type" not in gdf.columns:
                    gdf["osm_data_type"] = data_type
            else:
                poly = box(left, bottom, right, top)
                try:
                    gdf = ox.features_from_polygon(poly, tags=tags)
                except Exception as exc:
                    logger.error(f"[ERROR] Failed to fetch OSM data ({data_type}): {exc}")
                    continue

                if gdf is None or gdf.empty:
                    cache_file.touch(exist_ok=True)
                    time.sleep(delay)
                    continue

                gdf = gdf.reset_index(drop=True)
                gdf["osm_data_type"] = data_type
                gdf.to_file(cache_file, driver="GeoJSON")
                time.sleep(delay)
                # Copy the GeoDataFrame to avoid "I/O operation on closed file" error
                gdf = gdf.copy()

            road_types_only = config.get("road_types_only")
            if road_types_only and primary_tag in gdf.columns:
                gdf = gdf[gdf[primary_tag].isin(road_types_only)]
                gdf = gdf.reset_index(drop=True)
                if gdf.empty:
                    continue

            results.append(gdf)

    return results


def fetch_osm_features(
    vector_path: Optional[Union[str, Path]] = None,
    bbox: Optional[Union[str, Sequence[float]]] = None,
    output_path: Union[str, Path] = "data/output/osm_features.geojson",
    data_types: Optional[Sequence[str]] = None,
    max_tile_deg: Optional[float] = None,
    buffer_deg: Optional[float] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    input_crs: Optional[str] = None,
    delay: float = 1.0,
) -> Optional[gpd.GeoDataFrame]:
    """Download OSM features within a given extent."""
    if not vector_path and bbox is None:
        raise ValueError("Either vector_path or bbox must be provided")

    data_types = _validate_data_types(data_types)

    max_tile_deg = max_tile_deg or DEFAULT_OSM_CONFIG.get("max_tile_deg", 0.5)
    buffer_deg = buffer_deg if buffer_deg is not None else DEFAULT_OSM_CONFIG.get("buffer_deg", 0.01)

    cache_dir = Path(cache_dir or DEFAULT_OSM_CONFIG.get("cache_dir", "data/cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    clip_geometry: Optional[BaseGeometry] = None
    if vector_path:
        bounds, clip_geometry = _prepare_bounds_from_vector(vector_path, input_crs=input_crs)
    else:
        bounds = _parse_bbox_input(bbox)  # type: ignore[arg-type]

    left, bottom, right, top = bounds
    bbox_full: BBox = (
        left - buffer_deg,
        bottom - buffer_deg,
        right + buffer_deg,
        top + buffer_deg,
    )

    tiles = list(bbox_chunks(bbox_full, max_size_deg=max_tile_deg))
    results: List[gpd.GeoDataFrame] = []
    
    logger.info(f"开始下载 OSM 数据")
    logger.info(f"  • 范围: ({left:.4f}, {bottom:.4f}, {right:.4f}, {top:.4f})")
    logger.info(f"  • 数据类型: {', '.join(data_types)}")
    logger.info(f"  • 将范围分割为 {len(tiles)} 个 BBox 块")

    tile_results = _fetch_osm_for_bbox(tiles, data_types=data_types, cache_dir=cache_dir, delay=delay)
    # Copy each GeoDataFrame to avoid file handle issues
    tile_results = [gdf.copy() for gdf in tile_results]
    results.extend(tile_results)

    if not results:
        logger.warning("✗ 没有下载到任何 OSM 要素")
        return None

    # Concatenate all results
    logger.info(f"正在合并数据...")
    gdf_all = gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs="EPSG:4326")
    gdf_all = gdf_all[~gdf_all.geometry.is_empty]

    gdf_all["__geometry_wkt__"] = gdf_all.geometry.to_wkt()
    original_count = len(gdf_all)
    gdf_all = gdf_all.drop_duplicates(subset=["osm_data_type", "__geometry_wkt__"])
    gdf_all = gdf_all.drop(columns="__geometry_wkt__")
    dedup_count = original_count - len(gdf_all)
    if dedup_count > 0:
        logger.info(f"已去重 {dedup_count} 个重复要素")

    if clip_geometry is not None and not gdf_all.empty:
        logger.info(f"正在按矢量范围进行裁剪...")
        before_clip = len(gdf_all)
        clip_gdf = gpd.GeoDataFrame(geometry=[clip_geometry], crs="EPSG:4326")
        gdf_all = gpd.clip(gdf_all, clip_gdf)
        logger.info(f"  • 裁剪前: {before_clip}, 裁剪后: {len(gdf_all)}")

    driver = _infer_driver(output_path)
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"正在保存数据到 {output_path}...")
    gdf_all.to_file(output_path, driver=driver)

    logger.info(
        f"✓ [SUCCESS] 成功下载 {len(gdf_all)} 个要素 (数据类型: {', '.join(data_types)})"
    )
    return gdf_all


def fetch_osm_by_polygon(
    vector_path: Optional[Union[str, Path]] = None,
    output_path: Union[str, Path] = "data/output/osm_features.geojson",
    max_tile_deg: float = 0.5,
    buffer_deg: float = 0.01,
    roads_only: bool = True,
    cache_dir: Optional[Union[str, Path]] = None,
    data_types: Optional[Sequence[str]] = None,
    bbox: Optional[Union[str, Sequence[float]]] = None,
    input_crs: Optional[str] = None,
    delay: float = 1.0,
) -> Optional[gpd.GeoDataFrame]:
    """Backward-compatible helper that delegates to fetch_osm_features."""
    chosen_types = list(data_types) if data_types else None
    if chosen_types is None:
        chosen_types = ["road"] if roads_only else ["road"]
    return fetch_osm_features(
        vector_path=vector_path,
        bbox=bbox,
        output_path=output_path,
        data_types=chosen_types,
        max_tile_deg=max_tile_deg,
        buffer_deg=buffer_deg,
        cache_dir=cache_dir,
        input_crs=input_crs,
        delay=delay,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download OSM features by extent")
    parser.add_argument("--input", "-i", help="Input vector path (.shp / .geojson)")
    parser.add_argument(
        "--bbox",
        help="Manual bbox in WGS84 (left,bottom,right,top)",
    )
    parser.add_argument("--output", "-o", default="data/output/osm_features.geojson", help="Output path")
    parser.add_argument(
        "--data-types",
        "-t",
        nargs="+",
        help=f"OSM data types to download: {', '.join(sorted(OSM_DATA_TYPES.keys()))}",
    )
    parser.add_argument("--tile", type=float, default=0.5, help="Maximum tile size in degrees")
    parser.add_argument("--buffer", type=float, default=0.01, help="Buffer size in degrees")
    parser.add_argument("--cache-dir", type=str, default="data/cache", help="Cache directory")
    parser.add_argument("--input-crs", type=str, help="CRS of the input vector if missing (e.g. EPSG:3857)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")

    args = parser.parse_args()

    if not args.input and not args.bbox:
        parser.error("Either --input or --bbox must be provided")

    fetch_osm_features(
        vector_path=args.input,
        bbox=args.bbox,
        output_path=args.output,
        data_types=args.data_types,
        max_tile_deg=args.tile,
        buffer_deg=args.buffer,
        cache_dir=args.cache_dir,
        input_crs=args.input_crs,
        delay=args.delay,
    )

