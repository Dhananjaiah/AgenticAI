# Section 01: Introduction - What Is This Project?

## 🎯 Learning Goals
By the end of this section, you will understand:
- What an AI-powered insurance claims system does
- What "Agentic AI" means
- Why this project is useful
- The main components of the system

---

## 📺 Video Transcript

### Welcome to the Course!

Hello everyone! Welcome to our course on building an Agentic AI Insurance Claims System. My name is your instructor, and I'm really excited to take you through this journey.

Now, before we dive into the code, let's understand what we're building and why it matters.

### What Problem Are We Solving?

Imagine you work at an insurance company. Every day, hundreds of claims come in. Each claim has:
- Forms filled out by customers
- Photos of damaged property
- Medical reports
- Police reports
- Previous policy documents

These documents come from everywhere:
- Emails
- Uploaded files
- SharePoint folders
- Cloud storage

Now, here's the challenge: **How do you find all the documents related to one claim?** 

Traditionally, a human has to:
1. Search through multiple systems
2. Match documents manually
3. Check for duplicates
4. Summarize everything

This takes hours! And humans make mistakes when tired.

### Enter Agentic AI

This is where our project comes in. We use "Agentic AI" - think of it as a team of smart robots that work together.

**What does "Agentic" mean?**

Simple: An "Agent" is like a specialized worker. Just like in a company:
- You have a receptionist who handles incoming calls
- You have an accountant who handles money
- You have a manager who coordinates everyone

In our AI system:
- We have a **SQL Agent** that talks to the database
- We have a **SharePoint Agent** that reads SharePoint files
- We have a **Blob Agent** that retrieves files from cloud storage
- We have an **Orchestrator** that coordinates all of them

Each agent is good at one specific job. Together, they process claims automatically!

### What Does This System Actually Do?

Let me walk you through a typical scenario:

**Step 1: A claim comes in**
Someone files an insurance claim. Let's say their car was damaged.

**Step 2: Gather all documents**
Our AI agents go to work:
- SQL Agent: "Let me check the database for this claim number"
- SharePoint Agent: "I'll look for any uploaded documents"
- Blob Agent: "I'll search the cloud storage for photos"

**Step 3: Remove duplicates**
Sometimes the same document is in multiple places. Our "Deduplication Service" finds these duplicates and removes them.

**Step 4: Build a complete picture**
All the information is combined into one "Canonical Bundle" - a fancy way of saying "one complete package."

**Step 5: AI Summary (optional)**
If needed, an AI language model (like GPT-4) can read everything and write a summary.

### The Main Components

Here's a simple diagram of our system:

```
[User/Client]
     ↓
[API Gateway] ← This is where requests come in (FastAPI)
     ↓
[Orchestrator Agent] ← The "manager" that coordinates everything
     ↓
┌────────────────────────────────────┐
│  [SQL Agent] [SharePoint Agent] [Blob Agent]  │ ← The "workers"
└────────────────────────────────────┘
     ↓
[Vector Database + Cache + Main Database]  ← Where data is stored
     ↓
[LLM Service] ← AI that writes summaries (optional)
```

Don't worry if this seems complex. We'll explore each piece in detail in the coming sections!

### Why Use This Architecture?

**Question: Why not just have one program do everything?**

Great question! Here's why we use multiple agents:

1. **Easier to maintain**: If SharePoint changes, you only fix the SharePoint agent
2. **Easier to scale**: Need to process more claims? Add more agents
3. **Easier to test**: Test each agent separately
4. **More reliable**: If one agent fails, others keep working

This is called "microservices architecture" or "separation of concerns."

### Technologies We'll Use

Here's a quick overview of the tools:

| Technology | What it does |
|------------|--------------|
| Python 3.11+ | Our programming language |
| FastAPI | Creates the web API |
| Microsoft Autogen | Framework for AI agents |
| PostgreSQL | Main database |
| Redis | Fast cache |
| ChromaDB | Vector database for AI search |
| Docker | Runs everything in containers |

Don't worry if you don't know all of these. We'll explain each one!

### What's Next?

In the next section, we'll set up your computer to run this project. You'll install:
- Python
- Docker
- Required libraries

Then we can start coding!

---

## 📝 Key Takeaways

1. **Insurance claims** involve many documents from many sources
2. **Agentic AI** means having specialized AI workers (agents) that collaborate
3. **Orchestrator** is the manager that coordinates all agents
4. **Canonical Bundle** is the final, complete picture of a claim
5. **This system** automates what used to take humans hours

---

## ❓ Practice Questions

1. What does "Agentic" mean in the context of AI?
2. Name three types of agents in our system
3. What is a "Canonical Bundle"?
4. Why do we use multiple agents instead of one big program?

---

## 🔗 Related Code

These are the main files we'll explore:
- `app/main.py` - The entry point of our API
- `app/agents/orchestrator.py` - The manager agent
- `app/agents/retriever_sql.py` - The database agent
- `app/agents/retriever_sharepoint.py` - The SharePoint agent
- `app/agents/retriever_blob.py` - The cloud storage agent

---

[← Back to Course Home](../README.md) | [Next: Getting Started →](../section-02-getting-started/README.md)
