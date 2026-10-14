# StudyBuddy+

StudyBuddy+ is a Streamlit AI agent for university students in Uzbekistan. It helps manage schedules and exams, generate study tasks/plans, draft emails, and provide daily briefings.

## Features
- Chat in Uzbek/English/Russian
- Event management (class/exam/assignment/other)
- Weekly repeating classes
- `.ics` import/export
- Upcoming prep suggestions (7 days)
- Dashboard with urgency colors and progress bar
- Email drafting with `mailto:` link (never auto-sent)
- Study plan generator with revision day
- Safe calculator tool
- Web search tool hook for Anthropic web search

## Run locally
1. Create and activate a Python 3.10+ environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   streamlit run app.py
   ```
4. In sidebar, paste your own Anthropic API key

## Testing checklist (5 commands)
1. `Dushanba 09:00 da Python darsi qo'sh (har hafta takrorlansin).`
2. `Matematika imtihonim 2026-11-20. Nima tayyorlashim kerak?`
3. `Menga Professor Karimovga uzr so‘rab email draft yozib ber.`
4. `Fizika imtihoni uchun bugundan boshlab o‘qish rejasini tuz.`
5. `Kelasi 7 kun uchun daily briefing ber.`

## Build order mapping
1. Project structure and `requirements.txt`
2. Tool functions and JSON schemas
3. Agent loop (`run_agent`)
4. Dynamic system prompt
5. Streamlit UI (sidebar + chat + dashboard)
6. `.ics` import/export
7. Testing checklist with example commands
8. GitHub + Streamlit deployment steps

## Deploy to GitHub and Streamlit Community Cloud (click-by-click)
1. Open your GitHub repository page.
2. Click **Add file** → **Upload files** (or push from local git).
3. Upload at least: `app.py`, `requirements.txt`, `README.md`.
4. Commit changes to `main` (or your chosen branch).
5. Go to https://streamlit.io/cloud and sign in with GitHub.
6. Click **New app**.
7. Select repository: `SamadbekShuhratov/StudyBunny`.
8. Select branch.
9. Set **Main file path** to `app.py`.
10. Click **Deploy**.
11. After deploy, open the app URL.
12. In sidebar, paste your Anthropic API key and start testing.

## Privacy and safety
- Data stays in `st.session_state` (per-session only)
- API keys are never hardcoded
- Visible notice in app: **Emails are never sent automatically.**

## 7-slide presentation outline
1. **Title** – StudyBuddy+: AI Assistant for Student Success
2. **What is an AI Agent?** – Definition, tools, loop-based reasoning
3. **How it works** – User input → model → tool use → response
4. **How we built it** – Python + Anthropic SDK + Streamlit + session state
5. **My agent** – Schedule, tasks, dashboard, email drafting, study plans
6. **Demo** – 3-5 sample Uzbek commands and outputs
7. **Conclusion** – Value for students + public app link
