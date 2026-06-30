# LectureVoice

Turn your lecture slides into a narrated video — in your own voice. Upload your slides, record 60 seconds of yourself speaking, and LectureVoice generates a complete MP4 where every slide is narrated by an AI that sounds like you. Free, self-hosted, and runs entirely on your own computer or lab server.

---

## What you need before you start

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** — the only software you need to install. Everything else runs inside Docker.
- **A Gemini API key (free)** — LectureVoice uses Google's Gemini AI to write the narration scripts. Get a free key at [aistudio.google.com](https://aistudio.google.com/). If you'd rather run fully offline with no API key at all, see the Ollama option in [docs/runbook.md](docs/runbook.md).
- **An NVIDIA GPU (optional)** — Voice generation is much faster with a GPU (a 30-slide lecture takes roughly 5–8 minutes). Without one it still works, just slower (30–60 minutes on CPU).

---

## Setup (one time only)

Make sure Docker Desktop is running, then follow these three steps:

**Step 1 — Download and create the configuration file:**

```bash
git clone https://github.com/shaveenudayanga/voice-cloned-AI-lecture-video-generator.git
cd voice-cloned-AI-lecture-video-generator
make first-run
```

On the first run, `make first-run` creates a file called `backend/.env` and then stops so you can fill in your API key.

**Step 2 — Add your Gemini API key:**

Open `backend/.env` in a text editor. Find this line and paste in your key:

```
GEMINI_API_KEY=         ← paste your key here
```

Also replace the access key with any long random password (this keeps your installation private):

```
API_KEY=change-me-before-deploy   ← replace this
```

Save the file.

**Step 3 — Start the app:**

```bash
make first-run
```

This pulls all required Docker images and builds the app. On a fast internet connection (100 Mbps+) this takes **10–20 minutes** the first time — it downloads roughly 1.5 GB of images and compiles the frontend. On a slower connection allow 30+ minutes. Your browser opens automatically when it's ready. Subsequent starts (`make up`) are fast because images are cached.

**Next time**, start and stop with:

```bash
make up    # start
make down  # stop
```

---

## Try it with a sample lecture first

A ready-made 5-slide lecture on photosynthesis is included in [sample-content/](sample-content/). Use it on your first run so you can learn the workflow before uploading your own slides.

---

## Your first lecture video — step by step

1. **Open** [http://localhost:3000](http://localhost:3000) in your browser.
2. **Create a project** — click "Create new lecture video" and give it a name.
3. **Upload slides** — drag in your PDF or PowerPoint file (up to 50 MB). You can delete and re-upload until it looks right.
4. **Record your voice** — click Record and speak naturally for about 60 seconds. Read from any lecture notes, tell an anecdote, anything in your normal teaching voice. Click Stop when done. You can re-record as many times as you like.
   - After recording, the app plays back a short test sentence in your synthesized voice so you can confirm it sounds right before continuing.
   - **You only ever need to record once.** Your voice is saved and reused for every future lecture automatically.
5. **Review the scripts** — LectureVoice writes a narration script for each slide. Read through them; edit any slide freely. Click Save on each slide you change.
6. **Generate audio** — click Generate Audio. Each slide's narration is synthesized in your voice. You can play each one back and, if any sounds wrong, edit that slide's script and regenerate just that slide.
7. **Render the video** — click Render. LectureVoice assembles all the slides and audio into a single MP4. A subtitle file (.srt) is included automatically.
8. **Download** — click "Download video" to save the MP4 to your computer.

---

## Something not working?

See [docs/runbook.md](docs/runbook.md) for:
- How to add other faculty members
- How to use Ollama (fully offline, no API key)
- How to scale up for faster processing
- How to delete voice recordings (biometric data deletion procedure)
- Backup and restore instructions

## Want to understand how this works?

See [docs/architecture.md](docs/architecture.md).

---

**License:** Apache-2.0 | **Voice model licenses:** F5-TTS (CC-BY-NC-4.0), XTTS-v2 (CPML) — non-commercial educational use only. See [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).
