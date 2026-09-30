"""
Data pipeline for FreightIQ.

Layout
  provenance.py          the dataset registry; every number traces to an entry here
  audit_datasets.py      statistical and cross-file checks on every dataset
  build_weekly_panel.py  the modelling panel for Model 2 (leak-free features)
  build_corridor_table.py monthly corridor view for contract-horizon work
  build_congestion_dataset.py  the Model 1 dataset, one row per voyage
  fetchers/              free, no-key sources only; each returns real data or nothing
"""
