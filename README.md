# Wind Generation Forecast Dashboard

## 1. Product overview

This project is a pilot web application for a UK energy utility that needs to
buy electricity from the day-ahead wholesale market. The dashboard compares
national wind-generation forecasts with recorded wind generation so that a
power-purchasing team can:

1. Understand the latest forecast available when a day-ahead purchasing
   decision must be made.
2. Quantify forecast accuracy and account for expected forecast error when
   deciding how much additional power to procure.

The scope is intentionally limited to national wind data from Elexon BMRS and
delivery dates in January 2026. The application is an analysis and decision
support tool; it does not place trades or claim that its cutoff is the
client's official market deadline.

## 2. Live links and assignment deliverables

The following links should be replaced before submission:

- **Deployed application:** `TODO: add Vercel or Heroku URL`
- **Unlisted video demo:** `TODO: add YouTube unlisted URL`
- **Public GitHub repository:** `TODO: add anonymous public repository URL`
- **Submission form:** [Microsoft submission form](https://forms.cloud.microsoft/r/FTX6K2bbnU)

Before submitting, open the deployed application, video, and repository in an
incognito/private browser window and confirm that each has sufficient access.

The video should be no longer than 10 minutes:

- **Part 1, customer presentation (maximum 5 minutes):** demonstrate the
  dashboard, date selection, KPIs, chart, table, and customer value.
- **Part 2, technical review (maximum 5 minutes):** explain the architecture,
  API, data-selection rules, code structure, testing, Docker setup, and
  development practices.

## 3. Architecture

```text
Elexon BMRS
  FUELHH actuals       WINDFOR forecasts
          \             /
           FastAPI backend
           fetch + analyse
                    |
                    | GET /api/analysis?delivery_date=2026-01-15
                    v
             React/Vite dashboard
             KPIs + chart + table
```

The backend owns the business rules and returns a structured response. The
frontend owns user interaction and visualisation. Docker Compose runs the two
services together.

## 4. Data sources and analysis rules

The application uses these Elexon BMRS stream endpoints:

- [FUELHH actual generation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
- [WINDFOR forecast generation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)

Relevant fields are:

- `startTime`: delivery timestamp
- `generation`: generation in MW
- `fuelType`: actual fuel type; only `WIND` is included
- `publishTime`: forecast publication timestamp

For each selected delivery date:

1. The backend calculates an illustrative cutoff of 12:00 Europe/London on the
   previous calendar day.
2. Actual records are restricted to `fuelType == "WIND"`.
3. Timestamps are converted to UK time and records are restricted to the
   requested delivery date.
4. The half-hourly actual readings are averaged into hourly values to match the
   forecast frequency.
5. Forecasts published after the cutoff are excluded.
6. If multiple eligible forecasts exist for an interval, the latest eligible
   forecast is selected.
7. Forecast and actual values are matched by delivery time.
8. Error is calculated as `forecast - actual`.
9. Aggregate metrics use matched forecast/actual pairs only.

The dashboard reports average forecast, average actual, Mean Absolute Error
(MAE), and bias. Missing values are kept as missing rather than being replaced
with zero.

The noon cutoff is a configurable business assumption for this pilot. It must
be confirmed with the client before operational use.

## 5. Repository structure and important files

```text
.
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- analysis.py
|   |   |-- cache.py
|   |   |-- config.py
|   |   |-- elexon_client.py
|   |   `-- schemas.py
|   |-- tests/
|   |   |-- test_analysis.py
|   |   `-- test_elexon_client.py
|   |-- Dockerfile
|   |-- requirements.txt
|   `-- pytest.ini
|-- frontend/
|   |-- src/
|   |   |-- App.jsx
|   |   |-- index.css
|   |   |-- main.jsx
|   |   `-- services/api.js
|   |-- Dockerfile
|   |-- index.html
|   |-- package.json
|   `-- vite.config.js
|-- .env.example
`-- docker-compose.yml
```

### Backend

| File | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI application, CORS, validation, endpoints, caching, and response assembly |
| `backend/app/elexon_client.py` | Async calls to the FUELHH and WINDFOR Elexon streams |
| `backend/app/analysis.py` | Timezone handling, filtering, forecast selection, interval matching, and metrics |
| `backend/app/schemas.py` | Pydantic response models for consistent API output |
| `backend/app/cache.py` | Small in-memory cache for repeated requests |
| `backend/app/config.py` | Environment-based configuration |
| `backend/tests/test_analysis.py` | Tests for cutoff, selection, matching, missing data, and metrics |
| `backend/tests/test_elexon_client.py` | Tests for request ranges and timezone-aware filtering |

### Frontend

| File | Responsibility |
| --- | --- |
| `frontend/src/App.jsx` | Dashboard state, date filter, KPI cards, chart, table, loading, and error states |
| `frontend/src/services/api.js` | Browser request to the backend analysis endpoint |
| `frontend/src/index.css` | Responsive layout, navigation, panels, tables, buttons, and visual styling |
| `frontend/src/main.jsx` | React application entry point |

### Operations

| File | Responsibility |
| --- | --- |
| `docker-compose.yml` | Runs the backend and frontend services together |
| `backend/Dockerfile` | Builds the Python API container |
| `frontend/Dockerfile` | Builds and serves the production frontend |
| `.env.example` | Example environment variables |

## 6. API

### Health check

```http
GET /api/health
```

Example response:

```json
{
  "status": "ok",
  "service": "wind-forecast-api",
  "demo_mode": false
}
```

### Analysis

```http
GET /api/analysis?delivery_date=2026-01-15
```

The response contains the delivery date, decision cutoff, interval results,
metrics, record counts, data-quality information, retrieval time, source, and
demo-mode status.

## 7. Running locally

### Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- npm
- Docker Desktop, if using Docker Compose

### Option A: Docker Compose

From the repository root:

```powershell
docker compose up --build
```

Open:

- Dashboard: <http://localhost:5173>
- API: <http://localhost:8000>
- API health: <http://localhost:8000/api/health>

The Compose configuration uses live Elexon data by default. To work offline,
change `USE_DEMO_DATA` to `"true"` in `docker-compose.yml`.

### Option B: Run services separately

Start the backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:USE_DEMO_DATA="true"
uvicorn app.main:app --reload
```

In another terminal, start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

Set `USE_DEMO_DATA=false` to use the live Elexon service. The frontend uses
`VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.

## 8. Testing and validation

Run backend tests:

```powershell
cd backend
pytest
```

Build the frontend:

```powershell
cd frontend
npm run build
```

The tests focus on the important business rules: previous-day cutoff
calculation, latest eligible forecast selection, delivery-date filtering,
timezone handling, missing values, and Elexon request parameters.

## 9. Development practices

- Business logic is separated from API and presentation code.
- External API failures and invalid responses are surfaced explicitly.
- Timezone-aware timestamps are used for UK delivery and publication times.
- API responses are validated with Pydantic models.
- Repeated requests are reduced using a small in-memory cache.
- Frontend loading, error, empty-data, and demo-mode states are handled.
- Docker provides a repeatable local environment.
- Tests cover the core analysis rules without requiring live API responses.

## 10. Configuration

The available configuration values are documented in `.env.example`:

| Variable | Purpose |
| --- | --- |
| `FRONTEND_ORIGIN` | Allowed frontend origin for backend CORS |
| `USE_DEMO_DATA` | Enables synthetic data when set to `true` |
| `ELEXON_BASE_URL` | Base URL for the Elexon BMRS API |
| `REQUEST_TIMEOUT_SECONDS` | External API request timeout |
| `VITE_API_BASE_URL` | Backend URL used by the built frontend |

Do not commit credentials or private configuration values.

## 11. Limitations and future improvements

- Only January 2026 delivery dates are supported for this assignment.
- The noon cutoff is illustrative and must be confirmed with the client.
- Forecast and actual data availability depends on the Elexon BMRS service.
- The cache is in memory and is cleared when the backend restarts.
- The pilot has no authentication, database, trade execution, or alerting.
- A production version could add persistent storage, monitoring, configurable
  cutoff rules, additional renewable technologies, and role-based access.

## 12. AI assistance disclosure

Yes, AI assistance was used to develop this project. GitHub Copilot and other
AI-assisted development tools were used for code exploration, implementation
support, React styling, debugging support, test review, and documentation
drafting. The developer remained responsible for selecting the architecture,
defining the business rules, reviewing the generated suggestions, integrating
the changes, and validating the application with tests and builds.

The data sources, business rules, generated code, and deployment configuration
should be reviewed and validated by a human developer before operational use.
