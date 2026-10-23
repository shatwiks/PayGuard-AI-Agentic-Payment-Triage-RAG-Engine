# 🛡️ PayGuard AI: Agentic Payment Triage & RAG Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 15+](https://img.shields.io/badge/next.js-15+-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)

> **Autonomous multi-agent payment dispute triage, fraud risk assessment, and policy-grounded RAG resolution platform.**

---

## 📌 Overview

**PayGuard AI** is an enterprise-grade agentic workflow and retrieval-augmented generation (RAG) platform designed to handle complex payment exceptions, chargeback disputes, failed transaction triage, and fraud compliance in real-time.

By combining autonomous specialized AI agents with a high-fidelity vector search engine indexing regulatory protocols (Visa/Mastercard reason codes, NACHA, SEPA, PCI-DSS, internal merchant SLAs), PayGuard transforms high-friction payment triage into an automated, transparent, and auditable process.

---

## ⚡ Key Architecture & Features

### 1. 🤖 Multi-Agent Orchestration Swarm
- **Ingestion & Normalizer Agent:** Normalizes multi-rail payment payloads (Stripe, Adyen, UPI, FedNow, SWIFT, PayPal).
- **Dispute & Exception Triage Agent:** Classifies root causes (processing timeout, cardholder dispute, insufficient funds, merchant billing error).
- **Fraud & Risk Scoring Agent:** Performs anomaly detection, velocity checks, and risk scoring.
- **RAG Policy & Compliance Agent:** Fetches authoritative recovery rules, chargeback windows, and required evidence packages.
- **Human-in-the-Loop (HITL) Supervisor:** Flags high-value or edge-case transactions for human analyst approval with complete agent thought traces.
- **Resolution & Action Agent:** Auto-initiates refunds, submits evidence dossiers, generates customer communications, or routes to dispute clearinghouses.

### 2. 📚 Grounded Retrieval-Augmented Generation (RAG)
- Hybrid dense & sparse search over payment dispute rulebooks, compliance mandates, and merchant agreements.
- Citation tracking ensuring all resolution proposals cite specific sections of banking regulations or internal policies.
- Incident history indexing for semantic retrieval of previously resolved similar cases.

### 3. 🖥️ Interactive Command & Triage Console
- Real-time incident live feed with streaming agent reasoning logs.
- Interactive Case Investigation Dossier with audit trails and decision matrices.
- Dynamic Knowledge Base management for regulatory manuals and SLA contracts.
- Human review and approval gates for high-risk automated actions.

---

## 🚀 Tech Stack

- **Backend / Agent Engine:** Python 3.14+, FastAPI, LangGraph / CrewAI multi-agent patterns, Pydantic v2
- **Vector Search / RAG:** ChromaDB / Qdrant / FAISS, dense vector embeddings, hybrid keyword reranking
- **Frontend / Console:** Next.js 15, React 19, TypeScript, Vanilla CSS design tokens with Glassmorphic HUD aesthetic
- **Database & Queue:** PostgreSQL / SQLite (metadata & audit trails), Redis / In-memory event bus
- **Observability:** OpenTelemetry-compatible agent execution traces & audit logs

---

## 📂 Project Structure

```
PayGuard-AI-Agentic-Payment-Triage-RAG-Engine/
├── backend/                  # FastAPI & Agentic RAG Services
│   ├── agents/               # Multi-agent worker definitions & orchestrator
│   ├── rag/                  # Document loader, chunking, vector index & retriever
│   ├── api/                  # REST endpoints & WebSocket streams
│   ├── models/               # Pydantic schemas & database entities
│   └── data/                 # Sample regulatory manuals & transaction datasets
├── frontend/                 # Next.js Command & Triage Dashboard
│   ├── src/                  # App router, components, hooks, styles
│   └── public/               # Static assets & iconography
├── docs/                     # Architecture diagrams, API specs & case studies
├── tests/                    # Backend unit & integration test suites
└── README.md
```

---

## 🛠️ Quick Start

*Setup guides and environment configurations will be updated as modules are committed.*

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
