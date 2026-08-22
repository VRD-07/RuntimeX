# IntelPulse AI (RuntimeX)

## Team Members
* [Your Name / Team Member 1]
* [Team Member 2]
* [Team Member 3]

## Problem Statement
In today’s fast-paced tech landscape, tracking competitor updates, academic breakthroughs, and market signals manually is a slow, scattered, and error-prone process. Research teams often struggle to aggregate context-aware intelligence quickly enough to make strategic decisions.

## Project Description
**IntelPulse AI** is an Autonomous Research & Competitor Intelligence Platform powered by Agentic AI Frameworks. It streamlines the research workflow by automatically tracking competitors, summarizing ArXiv papers, and providing instant, context-aware executive insights through a beautifully designed, state-of-the-art dashboard.

## Technologies Used
* **Frontend**: React.js, Vite, Tailwind CSS, Framer Motion, Aceternity UI, Lucide React
* **Backend**: Python, FastAPI, Uvicorn
* **AI & NLU**: Claude 3.5 Sonnet / Opus / Haiku (Anthropic API integration)

## Features
* **Autonomous Scanning**: Automatically aggregate ArXiv research papers and competitor news based on custom keywords and scan depth.
* **Executive Intelligence Digest**: Automatically synthesize data into a downloadable Markdown executive report.
* **Interactive AI Analyst**: A conversational chat interface to ask strategic questions directly about the scanned data.
* **Premium UI/UX**: Deep dark mode with Aceternity UI elements, including streaming typewriter effects, glowing border gradients, and beautiful Bento Grid layouts.
* **Dynamic Engine Routing**: Real-time status badges for intelligent agent routing and fallback engine tracking.

## Installation & Setup Steps

### 1. Clone the repository
```bash
git clone https://github.com/VRD-07/RuntimeX.git
cd RuntimeX
```

### 2. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create your environment variables file:
   ```bash
   cp .env.example .env
   ```
   *(Add your Anthropic/OpenAI API keys to the `.env` file)*
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```

## How to Run the Project

You will need two terminal windows open to run the frontend and backend simultaneously.

**Terminal 1 (Backend):**
```bash
cd backend
uvicorn main:app --reload --port 8000
```
*The FastAPI backend will run on `http://localhost:8000`*

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
```
*The React frontend will run on `http://localhost:5173`*

## Screenshots / Demo Link
*Add your screenshots here! E.g.:*
> `![Landing Page](./screenshots/landing.png)`
> `![Dashboard](./screenshots/dashboard.png)`

---
*Built with ❤️ by the IntelPulse Team.*