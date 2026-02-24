# 🏠 CoHabitant  
### Expense and Intelligent Shared Living Management System

> A fully normalized **3NF database design** for managing shared living spaces, including expenses, chores, inventory, governance, and utility analytics.

---

## 📘 Course Information
- **Course:** DAMG 6210 – Database Management and Database Design  
- **Group Number:** 6  

**Team Members**
- Deep Prajapati  
- Tianyi Fan  
- Ashfaq Ahmed Mohd  

---

## 📌 Project Overview

**CoHabitant** is a data-driven system designed to simplify and automate shared living management. The platform supports:

- 💰 Expense tracking and splitting  
- 🧹 Chore assignment and monitoring  
- 📦 Shared & personal inventory management  
- 🏢 Property and lease management  
- 🗳️ House governance through proposals and voting  
- ⚡ Utility usage tracking and analytics  

The database schema is fully normalized to **Third Normal Form (3NF)** to ensure:
- Data integrity
- Minimal redundancy
- Scalability
- Efficient querying

---

## 🗂️ Logical Schema (3NF)

![CoHabitant Logical ERD](LogicalERDModel.svg)

> Ensure the SVG file is named **`CoHabitant_3NF_Logical_Schema.svg`** and placed in the repository root.

---

## 🔄 Conceptual ➜ Logical Model Changes

### 1. Atomic Attributes (1NF)
Composite attributes were decomposed:
- `Name` → `First_Name`, `Last_Name`
- `Address` → `Street_Address`, `City`, `State`, `Zip_Code`

### 2. Inheritance Mapping
Used **Table-Per-Type** strategy:
- PERSON → LANDLORD, TENANT  
- INVENTORY_ITEM → SHARED_ITEM, PERSONAL_ITEM  

Subtypes use the supertype key as both **PK and FK**.

### 3. Foreign Key Implementation
All **1:M relationships** implemented using Foreign Keys.

### 4. Standard Data Types
- `INT`
- `VARCHAR`
- `DATE`
- `DATETIME`
- `BOOLEAN`
- `DECIMAL(10,2)` for all financial data

---

## 🧩 Entity Groups

### 👤 User Management
- PERSON  
- LANDLORD  
- TENANT  

Tracks identity, roles, lease linkage, and tenant responsibility metrics.

---

### 🏢 Property & Occupancy
- PROPERTY  
- LEASE_AGREEMENT  
- SUB_LEASE  
- GUEST  

Supports occupancy control, lease documentation, and guest tracking.

---

### 📦 Inventory Management
- INVENTORY_ITEM  
- SHARED_ITEM  
- PERSONAL_ITEM  

Supports:
- Shared household supplies  
- Personal tenant items  
- Auto-replenishment flags

---

### 💰 Financial Management
- EXPENSE  
- EXPENSE_SHARE  
- PAYMENT  

Features:
- Expense splitting policies  
- Individual tenant liabilities  
- Payment tracking  
- Receipt storage

---

### 🧹 Chores & Governance
- CHORE_DEFINITION  
- CHORE_ASSIGNMENT  
- PROPOSAL  
- VOTE  

Enables:
- Fair chore distribution  
- Proof of completion  
- Household decision-making

---

### ⚡ Utility Analytics
- UTILITY_READING  

Tracks:
- Utility type
- Provider
- Meter values
- Consumption history

---

## 📐 Normalization Summary

### First Normal Form (1NF)
- All attributes are atomic  
- No repeating groups  
- Separate tables for multi-valued entities (e.g., GUEST)

---

### Second Normal Form (2NF)
- All tables use **single-column surrogate keys**
- No partial dependencies

---

### Third Normal Form (3NF)
- No transitive dependencies  

Examples:
- Landlord financial details stored only in `LANDLORD`
- Expense totals stored only in `EXPENSE`
- `EXPENSE_SHARE` stores only tenant-specific liability

---

## 🚀 Design Strengths

- Fully normalized relational design (3NF)
- Scalable for multi-property environments
- Supports real-world shared living scenarios
- Clear separation of concerns
- Ready for SQL implementation and backend integration

---

