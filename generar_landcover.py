"""
Script de generación única — ejecutar UNA VEZ antes de arrancar el servidor.
Genera data/landcover.geojson con las clases forestales y agrícolas de CORINE 2018
incluyendo Península, Baleares y Canarias.

Uso:
    python generar_landcover.py
"""

import geopandas as gpd
import pandas as pd
import json

FOREST_CODES = {
    '311': {'label': 'Bosque de frondosas',     'color': '#4ce600'},
    '312': {'label': 'Bosque de coníferas',     'color': '#267300'},
    '313': {'label': 'Bosque mixto',            'color': '#70a800'},
    '321': {'label': 'Pastizales naturales',    'color': '#d4e6a5'},
    '322': {'label': 'Brezales y matorrales',   'color': '#a8a800'},
    '323': {'label': 'Vegetación esclerófila',  'color': '#d4a46a'},
    '324': {'label': 'Matorral en transición',  'color': '#c8c800'},
    '211': {'label': 'Tierras de labor secano', 'color': '#ffffa8'},
    '242': {'label': 'Mosaico de cultivos',     'color': '#e6e600'},
}

print("Leyendo Península + Baleares...")
gdf = gpd.read_file('data/CLC2018_ES.gpkg', layer='CLC18_ES')
gdf = gdf[gdf['CODE_18'].isin(FOREST_CODES.keys())].copy()
print(f"  {len(gdf)} polígonos")

print("Leyendo Canarias...")
gdf_can = gpd.read_file('data/CLC2018_ES.gpkg', layer='CLC18_ES_Canarias')
gdf_can = gdf_can[gdf_can['CODE_18'].isin(FOREST_CODES.keys())].copy()
print(f"  {len(gdf_can)} polígonos")

print("Reproyectando a WGS84...")
gdf     = gdf.to_crs(epsg=4326)
gdf_can = gdf_can.to_crs(epsg=4326)

print("Combinando...")
gdf = pd.concat([gdf, gdf_can], ignore_index=True)
print(f"  Total: {len(gdf)} polígonos")

print("Simplificando geometría (tolerancia 0.005)...")
gdf['geometry'] = gdf['geometry'].simplify(0.005, preserve_topology=True)

print("Fusionando por clase (dissolve)...")
dissolved = gdf.dissolve(by='CODE_18').reset_index()
print(f"  {len(dissolved)} clases tras dissolve")

dissolved['color'] = dissolved['CODE_18'].map(lambda c: FOREST_CODES[c]['color'])
dissolved['label'] = dissolved['CODE_18'].map(lambda c: FOREST_CODES[c]['label'])

print("Exportando a GeoJSON...")
geojson = json.loads(dissolved[['geometry', 'CODE_18', 'color', 'label']].to_json())

with open('data/landcover.geojson', 'w', encoding='utf-8') as f:
    json.dump(geojson, f)

size_mb = len(json.dumps(geojson)) / 1024 / 1024
print(f"\n✓ Guardado en data/landcover.geojson")
print(f"  Tamaño: {size_mb:.1f} MB")
print(f"  Features: {len(geojson['features'])}")
print(f"  Clases incluidas:")
for feat in geojson['features']:
    p = feat['properties']
    print(f"    {p['CODE_18']} — {p['label']}")