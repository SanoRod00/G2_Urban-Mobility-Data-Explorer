import pandas as pd
from normalize import normalize

data = pd.DataFrame({
    "tpep_pickup_datetime": ["2019-01-01 00:00:00", "not a date"],
    "tpep_dropoff_datetime": ["2019-01-01 00:10:00", "2019-01-01 00:20:00"],
    "PULocationID": [132, 999],
    "DOLocationID": [161, 1],
    "fare_amount": [52.0, "abc"],
    "store_and_fwd_flag": ["N", "Y"],
})

result = normalize(data)

assert len(result) == 2
assert "pickup_zone" in result.columns
assert pd.isna(result["pickup_datetime"][1])
assert pd.isna(result["fare"][1])
assert result["store_and_forward"][1] == True
print("All tests passed!")