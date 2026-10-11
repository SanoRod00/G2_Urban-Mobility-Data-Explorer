## Run order
1. **Setup** (Python 3.10+)
```
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
```
2. **Data:** download the raw files from the drive into `data/raw/`.
3. **Pipeline** (Sano)
```python pipeline/convert_zones.py
   python pipeline/load_data.py
```
4. **Cleaning**

```python -m cleaning.validate
**Tests:** `python -m cleaning.test_validate` 
            `python -m algorithms.test_top_k`



