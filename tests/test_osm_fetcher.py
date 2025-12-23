"""OSM 下载功能测试。"""
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from core.osm_fetcher import fetch_osm_features


def test_osm_fetcher():
    """测试多类型 OSM 数据下载功能。"""
    test_polygon_path = Path("data/input/test_polygon.geojson")
    output_file = Path("data/output/test_output.geojson")

    if not test_polygon_path.exists():
        polygon = Polygon([
            (116.38, 39.90),
            (116.40, 39.90),
            (116.40, 39.92),
            (116.38, 39.92),
            (116.38, 39.90),
        ])
        gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")
        test_polygon_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(test_polygon_path, driver="GeoJSON")

    try:
        result = fetch_osm_features(
            vector_path=str(test_polygon_path),
            output_path=str(output_file),
            data_types=["road", "railway"],
            max_tile_deg=0.2,
            buffer_deg=0.01,
            cache_dir="data/cache",
        )

        if result is not None and not result.empty:
            print(f"[SUCCESS] 测试成功，下载了 {len(result)} 条要素")
            print(f"[INFO] 数据类型: {result['osm_data_type'].unique().tolist()}")
            return True

        print("[WARNING] 未下载到数据")
        return False

    except Exception as err:  # pragma: no cover
        print(f"[ERROR] 测试失败: {err}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_osm_fetcher()

