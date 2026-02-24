# 🏠 CoHabitant: Expense and Intelligent Shared Living Management System

📘 **Course:** DAMG 6210  
👥 **Group Number:** 6  

## 👤 Group Members
- Deep Prajapati  
- Tianyi Fan  
- Ashfaq Ahmed Mohd  

---

## 1️⃣ Logical Relational Schema (3NF)

*(The diagram below represents our fully normalized Third Normal Form logical schema, including all Primary Keys, Foreign Keys, and Data Types.)*

![CoHabitant Logical ERD](CoHabitant_3NF_Logical_Schema.svg)

> **Note:** Ensure your uploaded SVG file is named `CoHabitant_3NF_Logical_Schema.svg` or update this link accordingly.

---

## 2️⃣ Summary of Changes: Conceptual (P2) ➜ Logical Model (P3)

To convert the conceptual design into a strict **3NF relational schema**, the following improvements were made:

### 🔹 Composite Attributes Removed
To satisfy **1NF**, composite attributes were broken into atomic fields:
- `Name` ➜ `First_Name`, `Last_Name` (PERSON, GUEST)
- `Address` ➜ `Street_Address`, `City`, `State`, `Zip_Code` (PROPERTY)

### 🔹 Inheritance Resolution
Relational databases do not support EER inheritance directly.  
A **Table-Per-Type** approach was used:
- Subtypes: `LANDLORD`, `TENANT`, `SHARED_ITEM`, `PERSONAL_ITEM`
- Each subtype uses the supertype PK as both **PK and FK**

### 🔹 Explicit Foreign Keys
All **1:M relationships** were implemented using Foreign Keys on the “many” side.

### 🔹 Standard Data Types
SQL-standard types assigned:  
`INT`, `VARCHAR`, `DATE`, `DATETIME`, `BOOLEAN`, `DECIMAL(10,2)`  
💰 All financial values use `DECIMAL(10,2)`.

---

## 3️⃣ Logical Entities, Attributes, and Data Types

---

### 👤 A. User Management

#### 1. PERSON
- `Person_ID` (INT) – **PK**
- `First_Name` (VARCHAR(50))
- `Last_Name` (VARCHAR(50))
- `Email` (VARCHAR(100))
- `Phone_Number` (VARCHAR(20))

#### 2. LANDLORD
- `Landlord_ID` (INT) – **PK, FK → PERSON**
- `Bank_Details` (VARCHAR(255))
- `Tax_ID` (VARCHAR(50))

#### 3. TENANT
- `Tenant_ID` (INT) – **PK, FK → PERSON**
- `Lease_ID` (INT) – **FK → LEASE_AGREEMENT**
- `Current_Net_Balance` (DECIMAL(10,2))
- `Emergency_Contact` (VARCHAR(100))
- `Move_In_Date` (DATE)
- `Tenant_Responsibility_Score` (INT)

---

### 🏢 B. Property & Occupancy

#### 4. PROPERTY
- `Property_ID` (INT) – **PK**
- `Landlord_ID` (INT) – **FK**
- `Street_Address` (VARCHAR(150))
- `City` (VARCHAR(50))
- `State` (VARCHAR(50))
- `Zip_Code` (VARCHAR(20))
- `Max_Occupancy` (INT)
- `WiFi_Password` (VARCHAR(50))

#### 5. LEASE_AGREEMENT
- `Lease_ID` (INT) – **PK**
- `Property_ID` (INT) – **FK**
- `Start_Date` (DATE)
- `End_Date` (DATE)
- `Document_URL` (VARCHAR(255))

#### 6. SUB_LEASE
- `SubLease_ID` (INT) – **PK**
- `Tenant_ID` (INT) – **FK**
- `Start_Date` (DATE)
- `End_Date` (DATE)
- `Pro_Rated_Cost` (DECIMAL(10,2))

#### 7. GUEST
- `Guest_ID` (INT) – **PK**
- `Tenant_ID` (INT) – **FK**
- `First_Name` (VARCHAR(50))
- `Last_Name` (VARCHAR(50))
- `Arrival_Date` (DATE)
- `Is_Overnight` (BOOLEAN)

---

### 📦 C. Inventory System

#### 8. INVENTORY_ITEM
- `Item_ID` (INT) – **PK**
- `Item_Name` (VARCHAR(100))
- `Total_Quantity` (INT)
- `Category` (VARCHAR(50))
- `Storage_Location` (VARCHAR(100))

#### 9. SHARED_ITEM
- `Item_ID` (INT) – **PK, FK**
- `Property_ID` (INT) – **FK**
- `Low_Stock_Threshold` (INT)
- `Auto_Replenish_Flag` (BOOLEAN)

#### 10. PERSONAL_ITEM
- `Item_ID` (INT) – **PK, FK**
- `Tenant_ID` (INT) – **FK**
- `Is_Private` (BOOLEAN)

---

### 💰 D. Financial Management

#### 11. EXPENSE
- `Expense_ID` (INT) – **PK**
- `Paid_By_Tenant_ID` (INT) – **FK**
- `Total_Amount` (DECIMAL(10,2))
- `Date_Incurred` (DATE)
- `Split_Policy` (VARCHAR(50))
- `Receipt_Image` (VARCHAR(255))

#### 12. EXPENSE_SHARE
- `Share_ID` (INT) – **PK**
- `Expense_ID` (INT) – **FK**
- `Owed_By_Tenant_ID` (INT) – **FK**
- `Owed_Amount` (DECIMAL(10,2))
- `Status` (VARCHAR(20))

#### 13. PAYMENT
- `Payment_ID` (INT) – **PK**
- `Payer_Tenant_ID` (INT) – **FK**
- `Amount` (DECIMAL(10,2))
- `Payment_Date` (DATE)
- `Note` (VARCHAR(255))

---

### 🧹 E. Chores & Governance

#### 14. CHORE_DEFINITION
- `Chore_ID` (INT) – **PK**
- `Task_Name` (VARCHAR(100))
- `Description` (VARCHAR(255))
- `Difficulty_Weight` (INT)
- `Frequency` (VARCHAR(50))

#### 15. CHORE_ASSIGNMENT
- `Assignment_ID` (INT) – **PK**
- `Chore_ID` (INT) – **FK**
- `Assigned_Tenant_ID` (INT) – **FK**
- `Due_Date` (DATE)
- `Completion_Date` (DATE)
- `Status` (VARCHAR(20))
- `Proof_Image` (VARCHAR(255))

#### 16. PROPOSAL
- `Proposal_ID` (INT) – **PK**
- `Proposed_By_Tenant_ID` (INT) – **FK**
- `Description` (VARCHAR(255))
- `Cost_Threshold` (DECIMAL(10,2))
- `Status` (VARCHAR(20))

#### 17. VOTE
- `Vote_ID` (INT) – **PK**
- `Proposal_ID` (INT) – **FK**
- `Tenant_ID` (INT) – **FK**
- `Approval_Status` (BOOLEAN)
- `Vote_Timestamp` (DATETIME)

---

### ⚡ F. Utility Analytics

#### 18. UTILITY_READING
- `Reading_ID` (INT) – **PK**
- `Property_ID` (INT) – **FK**
- `Utility_Type` (VARCHAR(50))
- `Provider_Name` (VARCHAR(100))
- `Meter_Value` (DECIMAL(10,2))
- `Reading_Date` (DATE)

---

## 4️⃣ Normalization Report (Achieving 3NF)

### ✅ First Normal Form (1NF)
- All attributes are atomic  
- Each table has a unique Primary Key  
- No repeating groups  

**Examples:**
- Guests stored in a separate `GUEST` table  
- Address and Name split into atomic fields  

---

### ✅ Second Normal Form (2NF)
- All tables use single-column surrogate keys  
- No composite primary keys  

➡️ Partial dependencies are eliminated.

---

### ✅ Third Normal Form (3NF)
- No transitive dependencies  

**Examples:**

🔹 **Property–Landlord Separation**  
`PROPERTY` stores only `Landlord_ID`  
Sensitive data like bank details remain in `LANDLORD`.

🔹 **Expense Normalization**  
`EXPENSE_SHARE` references `EXPENSE` via FK and stores only:
- `Owed_Amount`
- `Status`

No redundant financial data stored.
