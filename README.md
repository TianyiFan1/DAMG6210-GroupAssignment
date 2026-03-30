# CoHabitant — Intelligent Shared Living & Expense Management System

> **DAMG 6210 — Database Management and Database Design**
> Northeastern University, Spring 2026
> Team: Deep Prajapati, Tianyi Fan, Ashfaq Ahmed Mohd

## Mission Statement

A centralized household management database that reduces conflict in shared living environments. The system integrates inventory tracking, expense splitting, chore scheduling, and democratic governance into a single source of truth — ensuring transparency and fairness among tenants while maintaining a digital paper trail for landlord interactions and lease compliance.

## Key Features

- **Splitwise-Style Financial Math** — Equal, custom, and consumption-based expense splitting with pairwise settle-up
- **AI Receipt Scanner** — Gemini-powered receipt parsing with auto-fill for amount, category, and split policy
- **Walled Garden Architecture** — Property-scoped tenant isolation at both application and database layers
- **System-Versioned Temporal Tables** — Automatic point-in-time audit history on all financial tables
- **Soft Delete Infrastructure** — `Is_Active` flag on all 18 tables; no data is ever physically removed
- **Centralized Error Logging** — `SYSTEM_ERROR_LOG` captures all SP failures with full error context
- **AES-256 Encryption** — Landlord PII (bank details, tax ID) encrypted via SQL Server certificate chain
- **Role-Based Access Control** — `auth_gate()` middleware enforces Tenant/Landlord page-level access
- **Connection Pooling** — ODBC-level pooling with `@st.cache_resource` singleton initialization
- **CI/CD Pipeline** — GitHub Actions running pytest + Docker build on every push

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit, Plotly |
| Backend | Python 3.11, pyodbc |
| Database | Microsoft SQL Server 2022 (Temporal Tables, AES-256) |
| AI | Google Gemini 2.5 Flash |
| DevOps | Docker, docker-compose, GitHub Actions |
| Testing | pytest, Hypothesis, pytest-mock |

## Quick Start

```powershell
# 1. Run SQL scripts in order (schema → psm → indexes → inserts → encryption)
# 2. cd streamlit_app && pip install -r requirements.txt
# 3. cp .streamlit/secrets.toml.template .streamlit/secrets.toml  (edit credentials)
# 4. streamlit run app.py
```

See [`streamlit_app/README.md`](streamlit_app/README.md) for detailed setup, Docker instructions, testing guide, and Azure deployment steps.

## Data Model

- **Conceptual Model:** [`ConceptualModel.svg`](ConceptualModel.svg)
- **Logical ERD:** [`LogicalERDModel.svg`](LogicalERDModel.svg)
- **Physical Schema:** [`schema-CoHabitant.svg`](schema-CoHabitant.svg)
- **Power BI Report:** [`visualization_report.pdf`](visualization_report.pdf)

## Architectural Hardening (Pre-Deployment Audit)

A full read-only re-audit identified 4 concurrency and correctness issues, all resolved:

| Severity | Finding | Fix |
|----------|---------|-----|
| Critical | Partial settlements left `Owed_Amount` unchanged → over-settlement | SP now reduces `Owed_Amount` by consumed amount on partial coverage |
| High | Soft-delete refunded already-settled shares (double-reverse) | Guard blocks deletion if any share is `'Paid'`; refund queries filter on `'Pending'` |
| Medium | UPDLOCK in caller/counterparty order → deadlock on opposite-direction settlements | Deterministic lock ordering by ascending `Tenant_ID` |
| Low | Voting page bypassed `AppState` | Migrated to `AppState()` + `auth_gate()` |

## Azure Deployment

Production deployment targets 100% Azure Free Tier:

| Component | Service | Tier |
|-----------|---------|------|
| Database | Azure SQL Database | Free (Gen5 Serverless, 2 vCores) |
| App Hosting | Azure App Service | F1 (Free Linux) |
| Container Registry | Docker Hub | Free |

The `azure_deploy/` folder contains Azure-ready SQL scripts (identical to the root scripts but with `USE CoHabitant;` removed for Azure SQL compatibility).

## Repository Structure

```
DAMG6210-GroupAssignment/
├── .github/workflows/main.yml       # CI pipeline
├── CoHabitant_schema.sql             # 18 tables + 3 temporal + error log
├── CoHabitant_psm_script.sql         # Views, UDFs, 5 SPs, trigger
├── CoHabitant_indexes_script.sql     # 5 filtered indexes
├── CoHabitant_inserts.sql            # Seed data
├── CoHabitant_encryption_script.sql  # AES-256 PII encryption
├── azure_deploy/                     # Azure-ready SQL scripts (USE removed)
│   ├── 01_schema.sql
│   ├── 02_indexes.sql
│   ├── 03_psm.sql
│   ├── 04_inserts.sql
│   └── 05_encryption.sql
├── docker-compose.yml                # Local dev stack
├── streamlit_app/                    # Full application (see inner README)
├── *.svg / *.md                      # ERD models
└── visualization_report.*            # Power BI deliverables
```
