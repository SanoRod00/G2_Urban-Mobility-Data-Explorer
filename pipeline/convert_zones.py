import geopandas as gpd

zones = gpd.read_file("data/raw/taxi_zones.shp")
print(zones.columns)

zones = zones.to_crs(epsg=4326)
zones.to_file("data/raw/taxi_zones.geojson", driver="GeoJSON")
print("done:" , len(zones), "zones")