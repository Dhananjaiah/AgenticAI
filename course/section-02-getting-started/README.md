# Section 02: Getting Started - Setup and Installation

## 🎯 Learning Goals
By the end of this section, you will be able to:
- Install all required software
- Set up your development environment
- Run the project locally
- Verify everything works

---

## 📺 Video Transcript

### Let's Set Up Your Computer!

Hello again! In this section, we're going to set up your computer so you can run this project. Don't worry - I'll guide you through every step.

### What You'll Need

Before we start, make sure you have:
- A computer (Windows, Mac, or Linux - all work!)
- An internet connection
- About 30 minutes of time
- Basic familiarity with the command line (terminal)

If you've never used a terminal before, that's okay! I'll show you exactly what to type.

### Step 1: Install Python 3.11+

First, we need Python. This is the programming language our project uses.

**On Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. Run the installer
4. **IMPORTANT**: Check the box that says "Add Python to PATH"
5. Click "Install Now"

**On Mac:**
```bash
# If you have Homebrew installed:
brew install python@3.11

# Or download from python.org
```

**On Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

**Verify it works:**
```bash
python --version
# Should show: Python 3.11.x or higher
```

### Step 2: Install Docker

Docker lets us run databases and other services easily. Think of it as running apps in their own little boxes.

**On Windows/Mac:**
1. Go to https://www.docker.com/products/docker-desktop/
2. Download Docker Desktop
3. Install and run it
4. You'll see a whale icon in your system tray when it's running

**On Linux:**
```bash
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER
# Log out and log back in
```

**Verify it works:**
```bash
docker --version
# Should show: Docker version 20.x or higher
```

### Step 3: Clone the Project

Now let's get the project code on your computer.

```bash
# Pick a folder where you want the project
cd ~/projects  # or wherever you like

# Clone the repository
git clone <repository-url>

# Go into the project folder
cd agentic-ai-claims
```

If you don't have git:
- Windows: Install Git for Windows
- Mac: `brew install git`
- Linux: `sudo apt install git`

### Step 4: Create a Virtual Environment

A virtual environment is like a clean room for your project. It keeps Python packages separate from other projects.

```bash
# Create the virtual environment
python -m venv venv

# Activate it (do this every time you work on the project!)

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

# You'll see (venv) at the start of your command line
```

When you see `(venv)` in your terminal, you know it's activated!

### Step 5: Install Python Packages

Now let's install all the Python libraries our project needs:

```bash
# This reads pyproject.toml and installs everything
pip install -e ".[dev]"
```

This might take a few minutes. You'll see lots of text scrolling by - that's normal!

**What's happening?**
- `pip` is Python's package installer
- `-e` means "editable mode" (useful for development)
- `.[dev]` means "install the project plus development tools"

### Step 6: Set Up Environment Variables

Environment variables are settings that change depending on where you run the code (your computer vs production server).

```bash
# Copy the example file
cp .env.example .env
```

Now open `.env` in your text editor. Let's look at what's inside:

```bash
# Database settings
DATABASE_URL=postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_db

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# LLM Mode - start with "stub" (no real AI API needed)
LLM_MODE=stub
```

For now, the default settings are fine. We'll customize these later!

### Step 7: Start the Infrastructure

We need PostgreSQL (database) and Redis (cache) running. Docker makes this easy!

```bash
# Go to the infra folder
cd infra

# Start the services
docker-compose up -d postgres redis

# Check they're running
docker-compose ps
```

You should see both services as "Up". 

**What's happening?**
- PostgreSQL is a powerful database that stores our claims data
- Redis is a super-fast cache that makes things speedy
- `-d` means "run in background" (detached mode)

### Step 8: Set Up the Database

Now let's create the database tables:

```bash
# Go back to the project root
cd ..

# Run database migrations
alembic upgrade head
```

**What's a migration?**
Think of it like a blueprint for the database. It tells PostgreSQL what tables to create.

### Step 9: Run the Application!

Finally, let's start our application:

```bash
# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
```

### Step 10: Test It's Working

Open your web browser and go to:

- http://localhost:8000 - Should show a welcome message
- http://localhost:8000/docs - Interactive API documentation!
- http://localhost:8000/health - Should show system health

If you see these pages, congratulations! 🎉 Everything is working!

### Quick Reference: Daily Commands

When you come back to work on the project:

```bash
# 1. Start Docker services
cd infra && docker-compose up -d && cd ..

# 2. Activate virtual environment
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate  # Windows

# 3. Start the API
uvicorn app.main:app --reload
```

When you're done:
```bash
# Stop the API: Ctrl+C

# Stop Docker services
cd infra && docker-compose down
```

### Troubleshooting Common Issues

**"Port 8000 already in use"**
```bash
# Try a different port
uvicorn app.main:app --reload --port 8001
```

**"Cannot connect to PostgreSQL"**
```bash
# Check Docker is running
docker ps
# Restart the services
cd infra && docker-compose restart
```

**"ModuleNotFoundError"**
```bash
# Make sure venv is activated (you should see (venv))
# Reinstall packages
pip install -e ".[dev]"
```

**"Permission denied" (Linux/Mac)**
```bash
sudo chmod +x script_name.sh
```

---

## 📝 Key Takeaways

1. **Python 3.11+** is our programming language
2. **Docker** runs our databases easily
3. **Virtual environment** keeps packages isolated
4. **pip install -e ".[dev]"** installs everything we need
5. **uvicorn** runs our web server
6. **localhost:8000/docs** shows interactive API docs

---

## ❓ Practice Questions

1. Why do we use a virtual environment?
2. What command starts the API server?
3. What port does our application run on by default?
4. How do you stop Docker services?

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Lists all Python packages we need |
| `.env.example` | Template for environment variables |
| `.env` | Your local settings (don't commit this!) |
| `infra/docker-compose.yml` | Defines Docker services |
| `alembic.ini` | Database migration settings |

---

[← Previous: Introduction](../section-01-introduction/README.md) | [Next: Architecture →](../section-03-architecture/README.md)
