# Mini Survey

A simple full-stack teaching project: a survey app with Python (Flask) backend and vanilla HTML+JavaScript frontend.

## Features
- Backend API: GET `/questions` (fetches 3 hardcoded questions), POST `/answers` (stores answers in memory).
- Frontend: Loads questions dynamically, renders a form, submits answers via fetch(), shows success message.
- No database, no build tools – everything runs locally.

## Setup & Run

1. Create a virtual environment:
   ```
   python -m venv .venv
   ```

2. Activate it:
   - Linux/macOS: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the app:
   ```
   python app.py
   ```

5. Open in browser: http://127.0.0.1:5000/

## How it Works
- Page loads → JS fetches questions from `/questions` → renders form.
- Fill form & submit → JS sends JSON to `/answers` → backend stores in memory → shows "Thank you!".
- Check `stored_answers` list in `app.py` (in console) to see submissions (resets on restart).

Great for learning Flask APIs, fetch(), and full-stack basics!
