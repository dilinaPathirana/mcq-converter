# Sinhala MCQ PDF → Excel — web version (Vercel)

A drag-and-drop web front end for the same converter as the desktop tool
(`sinhala_mcq_tool/`), packaged to deploy on Vercel. Send the deployed link
to anyone and they can convert their own PDFs — no Python install, no GUI
setup on their end.

Two modes, matching the desktop GUI's two tabs:
- **Simple** — one PDF → plain Q No / Question / Option 1–5 / Notes Excel.
- **Template** — Sinhala PDF (required) + English/Tamil PDFs of the same
  exam (optional) → the HTML-wrapped multi-language import format.

Nothing is stored server-side: each upload is processed in memory for that
one request and discarded when the request ends.

## Deploy — GitHub + Vercel dashboard (recommended, ~5 minutes)

1. **Create a GitHub repo** (free, if you don't have one): go to
   github.com → New repository → name it e.g. `mcq-converter` → Create.
2. **Push this folder to it.** From a terminal, inside this `mcq-web`
   folder:
   ```bash
   git init
   git add .
   git commit -m "Sinhala MCQ converter web app"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/mcq-converter.git
   git push -u origin main
   ```
3. **Import into Vercel:** go to vercel.com → sign up/log in (you can use
   your GitHub account to sign in, which also connects them automatically)
   → "Add New..." → "Project" → pick the `mcq-converter` repo → Deploy.
   Vercel auto-detects the Python/Flask app from `requirements.txt` and
   `api/index.py` — no extra config needed.
4. After a minute or two you'll get a live URL like
   `https://mcq-converter-yourname.vercel.app`. That's the link to send
   your friend.

Every time you `git push` again, Vercel automatically redeploys — so if you
later update the converter logic, just push and the live link updates
itself.

## Deploy — Vercel CLI (no GitHub needed)

If you have Node.js installed, you can skip GitHub entirely:
```bash
cd mcq-web
npx vercel        # first run: log in / create account, answer setup prompts
npx vercel --prod # deploy to your permanent production URL
```

## Notes / limits

- Max upload size is capped at 15 MB per PDF in `api/index.py`
  (`MAX_CONTENT_LENGTH`) — plenty for a typical exam paper; raise it if you
  ever need to.
- Vercel's free (Hobby) plan gives each function up to 60 seconds to run
  (already set via `vercel.json`) and generous monthly usage — fine for
  occasional personal use. If you and friends start using it heavily, you'd
  eventually want to check Vercel's current Hobby-plan usage limits.
- This web version only accepts PDF input (no `.md` fallback) — that's
  intentional: PDF mode is exact and font-aware, while `.md` mode is a
  best-effort guess, so it wasn't worth the added complexity/bundle size
  for a shared tool. Anyone using this should always upload the original
  PDF.
- If a friend's PDF uses a legacy Sinhala font not in `SINHALA_FONTS` in
  `api/mcq_core.py` (currently FM Abhaya / FM Samantha / FM Ganganee /
  FM Bindumathi), add it there and redeploy.
