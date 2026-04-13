"""
Script de generación única — ejecutar UNA VEZ antes de arrancar el servidor.
Descarga núcleos de población >= 500 hab de la API-Features del IGN,
simplifica geometrías y guarda en data/nucleos.geojson

Uso:
    python generar_nucleos.py
"""

import httpx
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

MIN_HABITANTES = 500  # umbral mínimo de habitantes
LIMIT          = 100  # features por página
BASE_URL       = "https://api-features.ign.es/collections/nuc/items"

def descargar_nucleos():
    features = []
    offset   = 0
    total    = None

    print(f"Descargando núcleos >= {MIN_HABITANTES} hab. de la API IGN...")

    with httpx.Client(timeout=60) as client:
        while True:
            r = client.get(BASE_URL, params={
                "f":      "json",
                "limit":  LIMIT,
                "offset": offset,
            })
            r.raise_for_status()
            data = r.json()

            if total is None:
                total = data.get("numberMatched", "?")
                print(f"  Total núcleos en la API: {total}")

            batch = data.get("features", [])
            if not batch:
                break

            # Filtrar por habitantes
            filtrados = [
                f for f in batch
                if (f["properties"].get("habitantes") or 0) >= MIN_HABITANTES
                and f.get("geometry")
            ]
            features.extend(filtrados)

            offset += LIMIT
            print(f"  Descargados {offset}/{total} — filtrados acumulados: {len(features)}", end="\r")

            # Si ya hemos descargado todos
            if len(batch) < LIMIT:
                break

    print(f"\n  Total núcleos con >= {MIN_HABITANTES} hab.: {len(features)}")
    return features

def procesar_y_guardar(features):
    print("Convirtiendo a GeoDataFrame...")

    rows = []
    for f in features:
        try:
            geom = shape(f["geometry"])
            p    = f["properties"]
            rows.append({
                "geometry":  geom,
                "nombre":    p.get("nombre", ""),
                "habitantes":p.get("habitantes", 0),
                "codine":    p.get("codine", ""),
                "cpro":      p.get("cpro", 0),
                "capital":   p.get("capital", ""),
                "tipo":      p.get("tipo", ""),
                "latitud":   p.get("latitud", 0),
                "longitud":  p.get("longitud", 0),
            })
        except Exception as e:
            continue

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    print(f"  {len(gdf)} núcleos en GeoDataFrame")

    print("Simplificando geometrías (tolerancia 0.0002)...")
    gdf["geometry"] = gdf["geometry"].simplify(0.0002, preserve_topology=True)

    print("Exportando a GeoJSON...")
    geojson = json.loads(gdf.to_json())

    with open("data/nucleos.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f)

    size_mb = len(json.dumps(geojson)) / 1024 / 1024
    print(f"\n✓ Guardado en data/nucleos.geojson")
    print(f"  Tamaño: {size_mb:.1f} MB")
    print(f"  Núcleos: {len(geojson['features'])}")
    print(f"  Campos: nombre, habitantes, codine, cpro, capital, tipo, latitud, longitud")

if __name__ == "__main__":
    features = descargar_nucleos()
    procesar_y_guardar(features)