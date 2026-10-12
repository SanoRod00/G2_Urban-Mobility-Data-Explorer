from app import app

client = app.test_client()

def test_all():
    
  r = client.get("/api/health")
  assert r.status_code == 200 and r.get_json() == {"status": "ok"}
  
  data = client.get("/api/zones").get_json()
  assert data["count"] == 265
  
  by_id = {z["zone_id"]: z for z in data["results"]}
  assert by_id[132]["zone"] == "JFK Airport"
  assert by_id[57]["has_polygon"] is False and by_id[57]["map_zone_id"] == 56
  assert by_id[104]["map_zone_id"] == 103 
  assert by_id[264]["map_zone_id"] is None
  
  shapes = client.get("/api/zones/geojson").get_json()
  assert shapes["type"] == "FeatureCollection"
  
  r = client.get("/api/stats/best-spots?weekday=2&hour=8&k=3")
  data = r.get_json()
  assert r.status_code == 200
  assert data["weekday_name"] == "Tuesday" and len(data["results"]) == 3
  first = data["results"][0]
  for name in ["rank", "zone_id", "map_zone_id", "borough", "revenue_per_minute", "zone", "trips"]:
    assert name in first, name
    
r = client.get("/api/stats/best-spots?weekday=9&hour=8")
assert r.status_code == 400 and r.get_json()["error"]["code"] == "bad_request"

r = client.get("/api/nothing")  
assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"

if __name__ == "__main__":
    test_all()
    print("All tests passed")