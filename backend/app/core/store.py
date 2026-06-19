"""
In-memory singleton — populated once during FastAPI lifespan startup.

All routers and services read from these module-level references.
Assignment happens in main.py lifespan; reads happen at request time.
"""
from __future__ import annotations

import pandas as pd

violations: pd.DataFrame = pd.DataFrame()
hotspots: pd.DataFrame = pd.DataFrame()
temporal: pd.DataFrame = pd.DataFrame()
by_station: pd.DataFrame = pd.DataFrame()
by_junction: pd.DataFrame = pd.DataFrame()

repeat_offenders: pd.DataFrame = pd.DataFrame()
