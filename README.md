# ChurnWatch AI

**Customer churn risk monitoring and explainable insights for banking teams.**

[**Live Demo**](https://churnwatch-web.onrender.com)

## 📄 Project Report

For a detailed overview of ChurnWatch AI, including the methodology, system architecture, implementation, and results, check out the full project report.

📑 [View ChurnWatch AI Project Report](<ChurnWatch_AI_Project_Report (2)_compressed.pdf>)

## Overview

ChurnWatch AI is a prototype that helps banking teams explore customer behavior, identify potential churn risk, and understand the signals behind each risk assessment. It combines a rule-based risk scoring engine with AI-generated explanations and a monitoring interface.

The project uses **synthetic customer data** for demonstration and development; its outputs should not be treated as validated production predictions.

## Features

- **Dashboard:** Overview of customer churn-risk distribution and key indicators.
- **Customer Explorer:** Browse customer profiles and investigate risk signals.
- **Customer Details:** Review an individual customer's behavioral indicators and risk assessment.
- **AI Analysis:** Generate human-readable explanations of churn-risk factors, with an optional Groq-powered explanation service.
- **Monitoring:** Track changes in customer behavior and risk over time.
- **Service Status:** View application service health information.

## How It Works

1. Synthetic customer profiles and behavioral snapshots are loaded.
2. A FastAPI backend evaluates churn-related indicators using a rule-based point system.
3. Customers are assigned a risk level based on their score.
4. The frontend presents scores, trends, and customer details.
5. AI explanations can help describe the observed risk factors when the configured provider is available.

### Risk Levels

| Risk level | Score |
| --- | --- |
| Low | 0–2 |
| Medium | 3–5 |
| High | 6+ |

These thresholds belong to the prototype's rule-based model and are not calibrated probabilities of churn.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Data & monitoring | Supabase |
| AI explanations | Groq (optional, with fallback behavior) |
| Deployment | Render (live web demo) |

## Live Demo

Visit **[ChurnWatch AI](https://churnwatch-web.onrender.com)**.

The deployed demo may take a moment to load depending on hosting conditions. Features that depend on the backend, database, or AI provider require those services to be configured and available.

## Local Development

The exact commands depend on the repository's folder structure and package scripts. A typical setup is:

### Frontend

```bash
npm install
npm run dev
```

If the frontend is in a subfolder, run these commands from that folder.

### Backend

Install the dependencies declared in the backend's requirements file, then start the FastAPI application using its actual module path. For example, **if** the entry point is `main.py` and exports `app`:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Configure the environment variables required by the repository before starting the services. These may include Supabase connection settings and a Groq API key. **Never commit `.env` files or API keys.**

## Deployment

The current public frontend is hosted on **Render**:

https://churnwatch-web.onrender.com

For a similar setup:

1. Push the project to GitHub.
2. Create a Render service for the frontend and configure its root directory, build command, and publish directory to match the repository (for a standard Vite build, the output is `dist`).
3. Deploy the FastAPI backend as a separate web service if required.
4. Configure the frontend's backend API base URL and the backend's allowed CORS origins.
5. Add required secrets through the hosting provider's environment-variable settings.
6. Test customer views, API calls, and monitoring after deployment.

## Project Scope

ChurnWatch AI is a demonstration of customer-risk exploration, explainable analysis, and monitoring workflows. It is **not** a production banking decision system. Risk scores and AI explanations should be reviewed and validated before any real-world use.

---

*Built as an AI-powered banking analytics prototype.*
