#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from osgeo import gdal, ogr, osr

from import_landcover_source import (
    CODE_FILTER,
    TARGETS,
    canonical_extract_dir,
    ensure_extracted_gdb,
    open_source_dataset,
    raw_zip_path,
    repo_root,
    validate_layers,
)

LAYER_NAMES = tuple(target.source_layer for target in TARGETS)
SAMPLE_ID_CANDIDATES = ("OBJECTID", "OBJECTID_1", "OID", "FID")
LABEL_FIELD_CANDIDATES = ("LABEL3", "LABEL3V18", "LABEL2", "LABEL2V18", "LABEL1", "LABEL1V18")

gdal.UseExceptions()
ogr.UseExceptions()


def make_spatial_ref(epsg: int) -> osr.SpatialReference:
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    if hasattr(srs, "SetAxisMappingStrategy") and hasattr(osr, "OAMS_TRADITIONAL_GIS_ORDER"):
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox debe tener formato minx,miny,maxx,maxy")
    try:
        minx, miny, maxx, maxy = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox debe contener cuatro números") from exc
    if minx >= maxx or miny >= maxy:
        raise argparse.ArgumentTypeError("bbox inválido: min debe ser menor que max")
    return minx, miny, maxx, maxy


def parse_point(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("point debe tener formato lat,lon")
    try:
        lat, lon = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("point debe contener latitud y longitud numéricas") from exc
    if not -90.0 <= lat <= 90.0:
        raise argparse.ArgumentTypeError("latitud fuera de rango [-90, 90]")
    if not -180.0 <= lon <= 180.0:
        raise argparse.ArgumentTypeError("longitud fuera de rango [-180, 180]")
    return lat, lon


def build_bbox_geometry(minx: float, miny: float, maxx: float, maxy: float) -> ogr.Geometry:
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(minx, miny)
    ring.AddPoint(maxx, miny)
    ring.AddPoint(maxx, maxy)
    ring.AddPoint(minx, maxy)
    ring.AddPoint(minx, miny)

    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    polygon.AssignSpatialReference(make_spatial_ref(4326))
    return polygon


def build_point_geometry(lat: float, lon: float) -> ogr.Geometry:
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(lon, lat)
    point.AssignSpatialReference(make_spatial_ref(4326))
    return point


def transform_geometry(geometry: ogr.Geometry, target_srs: osr.SpatialReference | None) -> ogr.Geometry:
    clone = geometry.Clone()
    source_srs = clone.GetSpatialReference()
    if target_srs is None or source_srs is None or source_srs.IsSame(target_srs):
        return clone

    transform = osr.CoordinateTransformation(source_srs, target_srs)
    result = clone.Transform(transform)
    if result != 0:
        raise RuntimeError("No se pudo transformar la geometría de consulta al SRC de la capa")
    return clone


def normalize_code(value: object) -> str:
    if value is None:
        return "<null>"
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text or "<vacío>"


def sort_code_key(code: str) -> tuple[int, object]:
    if code.isdigit():
        return (0, int(code))
    return (1, code)


def list_field_names(layer: ogr.Layer) -> list[str]:
    layer_defn = layer.GetLayerDefn()
    return [layer_defn.GetFieldDefn(index).GetNameRef() for index in range(layer_defn.GetFieldCount())]


def resolve_sample_id_field(layer: ogr.Layer) -> str | None:
    field_names = list_field_names(layer)
    normalized = {name.upper(): name for name in field_names}
    for candidate in SAMPLE_ID_CANDIDATES:
        resolved = normalized.get(candidate.upper())
        if resolved:
            return resolved
    return None


def resolve_label_field(layer: ogr.Layer) -> str | None:
    field_names = list_field_names(layer)
    normalized = {name.upper(): name for name in field_names}
    for candidate in LABEL_FIELD_CANDIDATES:
        resolved = normalized.get(candidate.upper())
        if resolved:
            return resolved
    for name in field_names:
        if name.upper().startswith("LABEL"):
            return name
    return None


def get_optional_field(feature: ogr.Feature, field_name: str | None) -> object:
    if not field_name:
        return None
    try:
        return feature.GetField(field_name)
    except KeyError:
        return None


def get_feature_sample_id(feature: ogr.Feature, sample_id_field: str | None) -> object:
    value = get_optional_field(feature, sample_id_field)
    if value is not None:
        return value
    return feature.GetFID()


def resolve_source_dataset(args: argparse.Namespace) -> tuple[Path, Path | None]:
    if args.source_dataset:
        source_dataset = Path(args.source_dataset).expanduser().resolve()
        if not source_dataset.exists():
            raise FileNotFoundError(f"Dataset fuente no encontrado: {source_dataset}")
        return source_dataset, None

    root_dir = repo_root()
    raw_zip = Path(args.raw_zip).expanduser().resolve() if args.raw_zip else raw_zip_path(root_dir).resolve()
    extracted_gdb_dir = (
        Path(args.extracted_gdb_dir).expanduser().resolve()
        if args.extracted_gdb_dir
        else canonical_extract_dir(root_dir).resolve()
    )
    source_dataset = ensure_extracted_gdb(raw_zip, extracted_gdb_dir)
    return source_dataset.resolve(), raw_zip


def create_code_summary(code: str) -> dict[str, object]:
    return {
        "code": code,
        "imported": code in CODE_FILTER,
        "feature_count": 0,
        "sample_objectids": [],
    }


def create_feature_record(
    feature: ogr.Feature,
    sample_id_field: str | None,
    label_field: str | None,
    code: str,
) -> dict[str, object]:
    feature_id = get_feature_sample_id(feature, sample_id_field)
    return {
        "code": code,
        "imported": code in CODE_FILTER,
        "feature_id": feature_id,
        "class_label": get_optional_field(feature, label_field),
    }


def update_samples(samples: list[object], value: object, max_items: int) -> None:
    if value is None or len(samples) >= max_items:
        return
    samples.append(value)


def summarize_layer(
    ds: ogr.DataSource,
    layer_name: str,
    query_geometry_wgs84: ogr.Geometry,
    sample_size: int,
) -> dict[str, object]:
    layer = ds.GetLayerByName(layer_name)
    if layer is None:
        raise RuntimeError(f"No se encontró la capa {layer_name} en el FileGDB")

    sample_id_field = resolve_sample_id_field(layer)
    label_field = resolve_label_field(layer)
    layer_query_geometry = transform_geometry(query_geometry_wgs84, layer.GetSpatialRef())
    layer.SetSpatialFilter(layer_query_geometry)
    layer.ResetReading()

    per_code: dict[str, dict[str, object]] = {}
    matched_features: list[dict[str, object]] = []
    total_features = 0
    imported_features = 0
    excluded_features = 0

    try:
        feature = layer.GetNextFeature()
        while feature is not None:
            feature_geometry = feature.GetGeometryRef()
            if feature_geometry is None or not feature_geometry.Intersects(layer_query_geometry):
                feature = layer.GetNextFeature()
                continue

            code = normalize_code(feature.GetField("CODE_18"))
            summary = per_code.setdefault(code, create_code_summary(code))
            summary["feature_count"] = int(summary["feature_count"]) + 1
            update_samples(summary["sample_objectids"], get_feature_sample_id(feature, sample_id_field), sample_size)
            matched_features.append(create_feature_record(feature, sample_id_field, label_field, code))

            total_features += 1
            if summary["imported"]:
                imported_features += 1
            else:
                excluded_features += 1

            feature = layer.GetNextFeature()
    finally:
        layer.SetSpatialFilter(None)
        layer.ResetReading()

    codes = sorted(per_code.values(), key=lambda item: sort_code_key(str(item["code"])))
    missing_codes = [str(item["code"]) for item in codes if not item["imported"]]
    return {
        "layer": layer_name,
        "sample_id_field": sample_id_field or "FID",
        "total_features": total_features,
        "imported_features": imported_features,
        "excluded_features": excluded_features,
        "codes": codes,
        "features": matched_features,
        "missing_codes": missing_codes,
    }


def build_combined_summary(layer_summaries: list[dict[str, object]], sample_size: int) -> dict[str, object]:
    combined: dict[str, dict[str, object]] = {}
    total_features = 0
    imported_features = 0
    excluded_features = 0

    for layer_summary in layer_summaries:
        total_features += int(layer_summary["total_features"])
        imported_features += int(layer_summary["imported_features"])
        excluded_features += int(layer_summary["excluded_features"])

        for code_summary in layer_summary["codes"]:
            code = str(code_summary["code"])
            merged = combined.setdefault(
                code,
                {
                    "code": code,
                    "imported": code in CODE_FILTER,
                    "feature_count": 0,
                    "sample_refs": [],
                },
            )
            merged["feature_count"] = int(merged["feature_count"]) + int(code_summary["feature_count"])
            for objectid in code_summary["sample_objectids"]:
                if len(merged["sample_refs"]) >= sample_size:
                    break
                merged["sample_refs"].append(f"{layer_summary['layer']}:{objectid}")

    codes = sorted(combined.values(), key=lambda item: sort_code_key(str(item["code"])))
    missing_codes = [str(item["code"]) for item in codes if not item["imported"]]
    return {
        "total_features": total_features,
        "imported_features": imported_features,
        "excluded_features": excluded_features,
        "codes": codes,
        "missing_codes": missing_codes,
    }


def build_output(
    query_mode: str,
    bbox: tuple[float, float, float, float] | None,
    point: tuple[float, float] | None,
    source_dataset: Path,
    raw_zip: Path | None,
    layer_summaries: list[dict[str, object]],
    sample_size: int,
) -> dict[str, object]:
    output = {
        "query_mode": query_mode,
        "source_dataset": str(source_dataset),
        "raw_zip": str(raw_zip) if raw_zip is not None else None,
        "import_filter": list(CODE_FILTER),
        "layers": layer_summaries,
        "combined": build_combined_summary(layer_summaries, sample_size),
    }
    if bbox is not None:
        output["bbox_epsg4326"] = list(bbox)
    if point is not None:
        output["point_epsg4326"] = {"lat": point[0], "lon": point[1]}
    return output


def format_codes_line(codes: list[str]) -> str:
    return ", ".join(codes) if codes else "ninguna"


def print_text_report(report: dict[str, object]) -> None:
    if report["query_mode"] == "bbox":
        bbox = report["bbox_epsg4326"]
        print(
            "BBox EPSG:4326: "
            f"{bbox[0]:.4f}, {bbox[1]:.4f} · {bbox[2]:.4f}, {bbox[3]:.4f}"
        )
    else:
        point = report["point_epsg4326"]
        print(f"Punto EPSG:4326: {point['lat']:.5f}, {point['lon']:.5f}")
    print(f"Dataset fuente: {report['source_dataset']}")
    if report["raw_zip"]:
        print(f"ZIP bruto: {report['raw_zip']}")
    print(f"Filtro actual CODE_FILTER ({len(report['import_filter'])}): {format_codes_line(report['import_filter'])}")
    print()

    for layer_summary in report["layers"]:
        print(
            f"[{layer_summary['layer']}] "
            f"{layer_summary['total_features']} features intersectadas "
            f"({layer_summary['excluded_features']} fuera del filtro actual)"
        )
        if not layer_summary["codes"]:
            if report["query_mode"] == "bbox":
                print("  Sin features en el bbox.")
            else:
                print("  Sin features en el punto.")
            print()
            continue
        sample_id_field = layer_summary["sample_id_field"]
        if report["query_mode"] == "point":
            for feature_summary in layer_summary["features"]:
                status = "importado" if feature_summary["imported"] else "NO importado"
                label = feature_summary["class_label"] or "-"
                print(
                    f"  {feature_summary['code']}: {label} · "
                    f"{status} · {sample_id_field}: {feature_summary['feature_id']}"
                )
        for code_summary in layer_summary["codes"]:
            status = "importado" if code_summary["imported"] else "NO importado"
            samples = ", ".join(str(item) for item in code_summary["sample_objectids"]) or "-"
            print(
                f"  {code_summary['code']}: {code_summary['feature_count']} feature(s) · "
                f"{status} · {sample_id_field} muestra: {samples}"
            )
        print(f"  Clases fuera del filtro actual: {format_codes_line(layer_summary['missing_codes'])}")
        print()

    combined = report["combined"]
    print("[Resumen combinado]")
    print(
        f"Total intersectado: {combined['total_features']} features "
        f"({combined['excluded_features']} fuera del filtro actual)"
    )
    for code_summary in combined["codes"]:
        status = "importado" if code_summary["imported"] else "NO importado"
        samples = ", ".join(str(item) for item in code_summary["sample_refs"]) or "-"
        print(
            f"  {code_summary['code']}: {code_summary['feature_count']} feature(s) · "
            f"{status} · muestras: {samples}"
        )
    print(f"Clases presentes fuera del filtro actual: {format_codes_line(combined['missing_codes'])}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspecciona el FileGDB original de CORINE en un bbox o en un punto y detecta "
            "clases CODE_18 presentes que no están en el CODE_FILTER actual."
        )
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "--bbox",
        type=parse_bbox,
        help="BBox en EPSG:4326 con formato minx,miny,maxx,maxy",
    )
    query_group.add_argument(
        "--point",
        type=parse_point,
        help="Punto del visor en formato lat,lon, por ejemplo 40.37742,-3.57650",
    )
    parser.add_argument(
        "--layer",
        dest="layers",
        action="append",
        choices=LAYER_NAMES,
        help="Capa del FileGDB a inspeccionar. Se puede repetir. Por defecto se inspeccionan todas.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Número máximo de identificadores de muestra por código y resumen combinado. Por defecto 5.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Formato de salida. Por defecto text.",
    )
    parser.add_argument(
        "--source-dataset",
        help="Ruta directa al FileGDB ya extraído. Si se informa, no se usa RAW_ZIP.",
    )
    parser.add_argument(
        "--raw-zip",
        help="Ruta al ZIP bruto CLC2018_GDB.zip. Si no se informa, usa RAW_ZIP o la ruta por defecto del repo.",
    )
    parser.add_argument(
        "--extracted-gdb-dir",
        help="Ruta del FileGDB extraído. Si no se informa, usa EXTRACTED_GDB_DIR o la ruta canónica del repo.",
    )
    args = parser.parse_args(argv)
    if args.sample_size < 1:
        parser.error("--sample-size debe ser mayor o igual que 1")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    selected_layers = args.layers or list(LAYER_NAMES)

    source_dataset, raw_zip = resolve_source_dataset(args)
    ds = open_source_dataset(source_dataset)
    validate_layers(ds)

    bbox = args.bbox if args.bbox else None
    point = args.point if args.point else None
    query_mode = "bbox" if bbox is not None else "point"
    query_geometry_wgs84 = build_bbox_geometry(*bbox) if bbox is not None else build_point_geometry(*point)
    layer_summaries = [
        summarize_layer(ds, layer_name, query_geometry_wgs84, args.sample_size)
        for layer_name in selected_layers
    ]
    report = build_output(query_mode, bbox, point, source_dataset, raw_zip, layer_summaries, args.sample_size)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
