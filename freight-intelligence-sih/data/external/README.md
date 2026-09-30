# `data/external/` — manually supplied data

Everything in this folder is fetched from an external publisher. Two of the three
fetchers are automated and free; the third cannot be, and this file explains why.

| File | Source | Automated? | Fetched by |
|---|---|---|---|
| `world_bank_pink_sheet.csv` | World Bank Pink Sheet (CC-BY 4.0) | yes | `python -m data_pipeline.fetchers.world_bank_prices` |
| `port_weather_daily.csv` | Open-Meteo archive API (CC-BY 4.0) | yes | `python -m data_pipeline.fetchers.open_meteo_weather` |
| `fx_usd_inr.csv` | ECB reference rates via Frankfurter (CC-BY 4.0) | yes | `python -m data_pipeline.fetchers.frankfurter_fx` |
| `bdi_subindices.csv` | Baltic Exchange | **no** | see below |

---

## `bdi_subindices.csv` — manual download required

**The Baltic Exchange does not redistribute this data for free, and no automated
route to it was found.** Every endpoint tried at build time refused:

| Source attempted | Result |
|---|---|
| `investing.com` historical data API | HTTP 403, Cloudflare challenge |
| `stooq.com` CSV endpoint | JavaScript challenge page |
| `fred.stlouisfed.org` (`BDI`) | connection timeout from this network |
| `balticexchange.com` | bot challenge page |
| Yahoo Finance (`^BDI`, `^BCI`, `^BPI`, `^BSI`, `^BHSI`) | no such listing |

Rather than ship a default value, the system marks this dataset `unavailable` and the
`baltic` feature group is **excluded from both models**. Nothing silently substitutes
a default index value.

### How to supply it

1. Download daily Baltic Exchange history from any of:
   - Baltic Exchange — Data Services → Market Information (subscription)
   - Barchart / Investing / MacroMicro free tier (one CSV download each)
2. Save the file into this folder as `bdi_subindices.csv`.
3. Validate and install it:
   ```
   python -m data_pipeline.fetchers.bdi_subindices --input <path-to-downloaded.csv>
   ```
4. Confirm:
   ```
   python -m data_pipeline.fetchers.bdi_subindices --status
   ```

### Expected schema

One row per day. Only `date` is required; the four class sub-indices are optional.

```csv
date,bdi,bci,bpi,bsi,bhsi
2024-01-02,1632,2380,1765,1460,712
2024-01-03,1610,2340,1740,1440,706
```

| Column | Required | Maps to |
|---|---|---|
| `date` | yes | as-of backward join onto the weekly panel |
| `bdi` | yes | general dry bulk index |
| `bci` | no | Capesize |
| `bpi` | no | Panamax |
| `bsi` | no | Supramax |
| `bhsi` | no | Handysize |

### What happens once it is installed

The `baltic` feature group switches on automatically and the panel gains
`bdi_ret_1w`, `bdi_ret_4w`, `bdi_vol_4w` and a per-vessel-class sub-index momentum.
Then **measure whether it helps** — do not assume it. On the current panel a
leave-one-group-out bootstrap found *no* feature group, including momentum, with an
effect separable from zero, so a new feature group may well fail the same test. The
ablation reports this automatically and the result is recorded in
`models/artifacts/freight_model_card.md`.

Note also that an independent audit of a comparable project found the Baltic index did
not improve that model's forecasts. Treat this as worth testing, not as an expected win.
