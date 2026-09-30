# FreightIQ — Maritime Decision Support

Dry bulk chartering decision support: freight rate forecasting, port congestion,
and the four recommendation pillars (market timing, vessel optimisation, idle
management, risk).

The full methodology, validation results and known limits are in
[`freight-intelligence-sih/METHODS.md`](freight-intelligence-sih/METHODS.md).
**Read that before quoting any number from this system.**

---

## Quick start

```bash
# 1. Backend dependencies
pip install -r freight-intelligence-sih/requirements.txt

# 2. Build data and train both models (fetches free external sources, ~2 min)
python freight-intelligence-sih/run_pipeline.py

# 3. Start the API
uvicorn backend.main:app --reload --app-dir freight-intelligence-sih
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### The static site

The website is a static single-page app at the repository root. It runs on its own
hard-coded data and needs no backend.

```bash
# Windows
run_website.bat          # opens index.html in the default browser
serve.ps1                # optional: serves over http://localhost:3000
```

To have the site show live model output instead, see
[Frontend ↔ backend](#frontend--backend) below.

---

## What to look at first

| Endpoint | What it tells you |
|---|---|
| `GET /api/data-coverage` | **Start here.** Which datasets are observed, derived, unverified or missing |
| `GET /api/model-report` | How both models were validated, with model cards |
| `GET /api/corridors` | Which corridors can be priced, and their observation windows |
| `GET /api/ports` | Congestion for every port with a line-up |
| `POST /api/query/route` | Full decision pack for one corridor |

---

## Repository layout

```
index.html, app.js, styles.css, assets/   the static single-page app
run_website.bat, serve.ps1                launchers for the static app

freight-intelligence-sih/
  backend/          FastAPI app; every response carries provenance + confidence
  models/
    model_1_congestion/   port congestion (predicts the PORT'S ESTIMATE of stay)
    model_2_freight/      freight rate forecasting (walk-forward validated)
  data_pipeline/
    provenance.py         the dataset registry; every number traces to an entry
    audit_datasets.py     statistical + cross-file integrity checks
    build_*.py            build the modelling panels
    fetchers/             free, no-key sources only
  data/                    inputs; see data/external/README.md for the manual one
  models/artifacts/        trained models, metrics and model cards
  services/                the four recommendation pillars
  tests/                   30 integrity tests
  METHODS.md               methodology, validation, limits
```

---

## Two things to know before you present this

**1. The freight rate data is unverified.** `data/training_matrix.csv` has no
identifiable source, and its statistical structure is inconsistent with independently
assessed market data — lanes hold near-constant ratios to each other, and
unrelated supply basins correlate at 0.90 on the modelling target. It is labelled
`tier: unverified` and every Model 2 metric inherits that caveat. See
[`data_pipeline/provenance.py`](freight-intelligence-sih/data_pipeline/provenance.py)
for the full findings.

**2. Model 1 predicts the port's estimate, not reality.** The line-up data contains
no actual completion or departure field, so realised turnaround cannot be measured
from it. A per-port median currently beats every fitted candidate on held-out data,
and that is what is deployed.

Neither of these is hidden in a footnote. The coverage endpoint reports both.

---

## Frontend ↔ backend

The static app originally had no connection to the API. It now calls the backend for
the model-status and data-coverage panels, and **falls back to the built-in data
when the backend is not running**, so opening `index.html` directly still works.

To use live data, start the backend first (step 3 above) and serve the app over HTTP
rather than opening the file directly, because browsers block `fetch` from `file://`:

```bash
powershell -File serve.ps1
```

Then open <http://localhost:3000/>.

---

## What would most improve this

1. Confirm or replace the freight rate data — everything in Model 2 rests on it.
2. Add an actual completion/departure field to the port line-ups.
3. Add rate history for the missing lanes (US, Australia, Indonesia, Mozambique,
   Handysize). The API returns `available: false` for these rather than guessing.
4. `data/external/bdi_subindices.csv` — see
   [`data/external/README.md`](freight-intelligence-sih/data/external/README.md).
