# Co-Habit — Intelligent Shared Living & Expense Management System

## Mission Statement
To design and implement a centralized household management database that reduces conflict in shared living environments. The system integrates inventory tracking, expense splitting, and chore scheduling into a single source of truth, ensuring transparency and fairness among tenants while maintaining a digital paper trail for landlord interactions and lease compliance.

## Mission Objectives

### 1) Smart Inventory & Auto-Replenishment
- Track shared consumable items (e.g., Toilet Paper, Dish Soap, Olive Oil) with low-stock thresholds.
- Differentiate between **Personal** inventory (e.g., "My Yogurt") and **Shared** inventory (e.g., "Our Milk") to prevent unauthorized consumption.

### 2) Multi-Model Expense Splitting
- Log household purchases and generate debts using variable logic (Equal Split, Consumption-Based, Fixed Ratio).
- Maintain a running **net balance** ledger between roommates to minimize transfers.

### 3) Dynamic Chore Roster & Verification
- Assign tasks via rotating schedule (Round Robin) or weighted burden rules.
- Require **proof of completion** (timestamp/photo) before a task moves from Pending to Done.

### 4) Sub-Lease & Guest Management
- Track authorized guests and overnight stays to comply with lease guest policies.
- Manage sub-letters with fixed date ranges and auto-calculate pro-rated utility shares.

### 5) Utility Usage Analytics
- Store monthly meter readings for Electricity/Gas/Water.
- Calculate daily average costs to detect usage spikes and correlate with seasons/behaviors.

### 6) Asset & Damage Log
- Maintain landlord asset registry (furniture/appliances) and condition history.
- Log incidents (e.g., broken window) with photos and timestamps for deposit dispute protection.

### 7) Voting & House Agreements
- Record house rules and voting records for major decisions (e.g., buying a microwave).
- Require recorded approval for financial decisions exceeding a threshold (e.g., $50+).
