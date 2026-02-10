# CoHabitant — Conceptual Database Model (EER)

## 📌 Overview

**CoHabitant** is a system designed to remove friction, disputes, and inefficiencies in shared living environments by introducing transparency, accountability, and structured governance for roommates.

This conceptual model uses **Enhanced Entity-Relationship (EER)** design to solve real-world problems in:

- Shared expense management
- Inventory tracking (personal vs shared)
- Chore accountability
- Lease and sub-lease compliance
- Democratic household decision-making

---

## ❗ Business Problems Addressed

### 💰 Financial Opacity & Inequality
Roommates struggle to track shared expenses and fairly split costs, leading to unresolved debts.

### 🧴 Inventory Mismanagement
No distinction between personal and shared items causes unauthorized use and supply shortages.

### 🧹 Chore Accountability
Verbal agreements fail. No proof of task completion leads to unfair workload distribution.

### 🏠 Lease & Sub-lease Compliance
Manual tracking of guests and subletters risks lease violations and incorrect cost calculations.

### 🗳️ Democratic Decision Making
No formal voting system for major purchases leads to disputes.

---

## 🧩 Entities, Attributes, and Relationships (EER)

### A. User Management (EER Inheritance)

#### 1. PERSON (Supertype)
**Attributes:** Name, Email, Phone Number  
**Relationships:** Parent of LANDLORD and TENANT (disjoint)

#### 2. LANDLORD (Subtype of PERSON)
**Attributes:** Bank Details, Tax ID  
**Relationships:** Owns one or many PROPERTIES

#### 3. TENANT (Subtype of PERSON)
**Attributes:**  
Current Net Balance, Emergency Contact, Move-In Date, Chore Weight Factor

**Relationships:**
- Signs one LEASE AGREEMENT
- Manages SUB-LEASES
- Invites GUESTS
- Owns PERSONAL ITEMS
- Logs EXPENSES
- Owes EXPENSE SHARES
- Transfers PAYMENTS
- Completes CHORE ASSIGNMENTS
- Raises PROPOSALS
- Casts VOTES

---

### B. Property & Occupancy

#### 4. PROPERTY
**Attributes:** Address, Max Occupancy, WiFi Password  
**Relationships:**
- Has one active LEASE AGREEMENT
- Stocks SHARED ITEMS
- Monitors UTILITY READINGS

#### 5. LEASE AGREEMENT
**Attributes:** Start Date, End Date, Document URL  
**Relationships:** Connects PROPERTY and TENANT

#### 6. SUB-LEASE
**Attributes:** Start Date, End Date, Pro-Rated Cost  
**Relationships:** Managed by a TENANT

#### 7. GUEST
**Attributes:** Name, Arrival Date, Is Overnight?  
**Relationships:** Linked to TENANT

---

### C. Inventory System (EER Inheritance)

#### 8. INVENTORY ITEM (Supertype)
**Attributes:** Item Name, Total Quantity, Category, Storage Location

#### 9. SHARED ITEM (Subtype)
**Attributes:** Low Stock Threshold, Auto-Replenish Flag  
**Relationships:** Stocked by PROPERTY

#### 10. PERSONAL ITEM (Subtype)
**Attributes:** Is Private  
**Relationships:** Owned by TENANT

---

### D. Financial Management

#### 11. EXPENSE
**Attributes:** Total Amount, Date Incurred, Split Policy, Receipt Image  
**Relationships:** Logged by TENANT → split into EXPENSE SHARES

#### 12. EXPENSE SHARE
**Attributes:** Owed Amount, Status (Paid/Unpaid)  
**Relationships:** Links EXPENSE to TENANT

#### 13. PAYMENT
**Attributes:** Amount, Date, Note  
**Relationships:** Made by TENANT to settle debts

---

### E. Chores & Governance

#### 14. CHORE DEFINITION
**Attributes:** Task Name, Description, Difficulty Weight, Frequency  
**Relationships:** Creates CHORE ASSIGNMENTS

#### 15. CHORE ASSIGNMENT
**Attributes:** Due Date, Completion Date, Status, Proof Image  
**Relationships:** Assigned to TENANT

#### 16. PROPOSAL
**Attributes:** Description, Cost Threshold, Status  
**Relationships:** Raised by TENANT, receives VOTES

#### 17. VOTE
**Attributes:** Approval Status, Timestamp  
**Relationships:** Cast by TENANT on PROPOSAL

---

### F. Utility Analytics

#### 18. UTILITY READING
**Attributes:** Utility Type, Provider Name, Meter Value, Reading Date  
**Relationships:** Monitored by PROPERTY

---

## 🧠 Key Design Decisions

### ✅ EER Inheritance for Actors
Separating PERSON into TENANT and LANDLORD avoids null attributes and keeps role-specific data clean.

### ✅ EER Inheritance for Inventory
Differentiates SHARED vs PERSONAL items to enforce privacy and auto-replenishment logic.

### ✅ Expense vs Expense Share Separation
Allows complex split rules and accurate debt tracking between roommates.

### ✅ Chore Verification Workflow
Proof Image ensures accountability before marking tasks complete.

### ✅ Democratic Proposal System
PROPOSAL + VOTE creates a digital paper trail for household decisions over $50.

---

## 📊 Conceptual EER Diagram

> The diagram below represents the full conceptual model.

![EER Diagram](./ConceptualModel.svg)
