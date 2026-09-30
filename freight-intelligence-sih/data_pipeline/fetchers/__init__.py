"""
Free, no-key market data fetchers.

Design rules (deliberate, after auditing what was here before):
  * Every fetcher either returns real data or returns None plus a reason.
  * Nothing returns a default number. A missing source must be visible as missing.
  * Nothing is fetched at API request time. Run these offline; the models and the
    API read the cached CSVs under data/external/.

Usage:
    python -m data_pipeline.fetchers.world_bank_prices
    python -m data_pipeline.fetchers.open_meteo_weather
    python -m data_pipeline.fetchers.frankfurter_fx
    python -m data_pipeline.fetchers.bdi_subindices
"""
