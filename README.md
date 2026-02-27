# SmartLoan 360

AI-powered loan eligibility and bank recommendation system built with Flask.

## Features

- Secure login session (`admin / smartloan360` demo credentials)
- Financial profile builder with live disposable income and EMI preview
- ML + rules-based loan decision (`APPROVED`, `CONDITIONAL`, `REJECTED`)
- Risk labeling with explainable reasons and cautions
- Multi-bank offer marketplace with interest, EMI, FOIR, and best recommendation

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open: `http://127.0.0.1:5000`

## GitHub Setup

1. Create a new empty GitHub repo (for example: `smartloan360`).
2. In project root (`f:\internship\smartloan360`), run:

```powershell
git init
git add .
git commit -m "Initial SmartLoan360 project"
git branch -M main
git remote add origin https://github.com/<your-username>/smartloan360.git
git push -u origin main
```

If Git is not installed, install Git first, then run the same commands.

## Deploy on Render via GitHub

### Option A: One-click using `render.yaml`

1. Open Render dashboard.
2. Click `New +` -> `Blueprint`.
3. Connect your GitHub account and select this repository.
4. Render reads `render.yaml` and creates the web service automatically.

### Option B: Manual Web Service

1. `New +` -> `Web Service`.
2. Select GitHub repo `smartloan360`.
3. Configure:
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Add environment variable:
   - `SECRET_KEY` = any long random string
5. Click `Create Web Service`.

## Deployment Files Included

- `Procfile` -> `web: gunicorn app:app`
- `runtime.txt` -> Python runtime pin
- `render.yaml` -> Render blueprint config
- `.gitignore` -> clean Git tracking

## Main Files

- `app.py` - Flask app, auth, scoring logic, and recommendations
- `run.py` - local startup entry
- `templates/` - login, dashboard, result UI
- `static/css/style.css` - responsive styling
- `static/js/main.js` - live dashboard calculations
