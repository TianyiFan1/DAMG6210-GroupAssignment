USE CoHabitant;
GO

-- 1. PERSON (20 rows total: 10 Landlords, 10 Tenants)
SET IDENTITY_INSERT dbo.PERSON ON;
INSERT INTO dbo.PERSON (Person_ID, First_Name, Last_Name, Email, Phone_Number) VALUES
(1, 'Alice', 'Smith', 'alice.landlord@email.com', '555-0101'),
(2, 'Bob', 'Jones', 'bob.properties@email.com', '555-0102'),
(3, 'Charlie', 'Brown', 'cbrown.investments@email.com', '555-0103'),
(4, 'Diana', 'Prince', 'dprince.realestate@email.com', '555-0104'),
(5, 'Evan', 'Wright', 'ewright.mgmt@email.com', '555-0105'),
(6, 'Fiona', 'Gallagher', 'fiona.g@email.com', '555-0106'),
(7, 'George', 'Costanza', 'vandelay.ind@email.com', '555-0107'),
(8, 'Hannah', 'Abbott', 'habbott.rentals@email.com', '555-0108'),
(9, 'Ian', 'Malcolm', 'chaos.theory.props@email.com', '555-0109'),
(10, 'Julia', 'Child', 'jchild.estates@email.com', '555-0110'),
(11, 'Kevin', 'Malone', 'kmalone.tenant@email.com', '555-0201'),
(12, 'Laura', 'Palmer', 'lpalmer.tenant@email.com', '555-0202'),
(13, 'Michael', 'Scott', 'mscott.tenant@email.com', '555-0203'),
(14, 'Nina', 'Tucker', 'ntucker.tenant@email.com', '555-0204'),
(15, 'Oscar', 'Martinez', 'omartinez.tenant@email.com', '555-0205'),
(16, 'Pam', 'Beesly', 'pbeesly.tenant@email.com', '555-0206'),
(17, 'Quinn', 'Fabray', 'qfabray.tenant@email.com', '555-0207'),
(18, 'Ryan', 'Howard', 'rhoward.tenant@email.com', '555-0208'),
(19, 'Stanley', 'Hudson', 'shudson.tenant@email.com', '555-0209'),
(20, 'Toby', 'Flenderson', 'tflenderson.tenant@email.com', '555-0210');
SET IDENTITY_INSERT dbo.PERSON OFF;
GO

-- 2. LANDLORD
INSERT INTO dbo.LANDLORD (Landlord_ID, Bank_Details, Tax_ID) VALUES
(1, 'Chase Bank - Acct 1234', 'TAX-111'),
(2, 'Bank of America - Acct 5678', 'TAX-222'),
(3, 'Wells Fargo - Acct 9012', 'TAX-333'),
(4, 'CitiBank - Acct 3456', 'TAX-444'),
(5, 'Capital One - Acct 7890', 'TAX-555'),
(6, 'Discover - Acct 2345', 'TAX-666'),
(7, 'US Bank - Acct 6789', 'TAX-777'),
(8, 'PNC Bank - Acct 0123', 'TAX-888'),
(9, 'TD Bank - Acct 4567', 'TAX-999'),
(10, 'Truist - Acct 8901', 'TAX-000');
GO

-- 3. PROPERTY
SET IDENTITY_INSERT dbo.PROPERTY ON;
INSERT INTO dbo.PROPERTY (Property_ID, Landlord_ID, Street_Address, City, State, Zip_Code, Max_Occupancy, WiFi_Password) VALUES
(1, 1, '123 Maple St', 'Boston', 'MA', '02115', 4, 'mapleTree123'),
(2, 2, '456 Oak Ave', 'Boston', 'MA', '02116', 3, 'oakWood456'),
(3, 3, '789 Pine Blvd', 'Cambridge', 'MA', '02139', 5, 'pineCone789'),
(4, 4, '101 Elm St', 'Somerville', 'MA', '02144', 2, 'elmLeaf101'),
(5, 5, '202 Cedar Rd', 'Brookline', 'MA', '02446', 4, 'cedarBranch202'),
(6, 6, '303 Birch Ln', 'Boston', 'MA', '02115', 6, 'birchBark303'),
(7, 7, '404 Ash Dr', 'Cambridge', 'MA', '02138', 3, 'ashTray404'),
(8, 8, '505 Spruce Ct', 'Somerville', 'MA', '02143', 4, 'spruceGoose505'),
(9, 9, '606 Walnut Pl', 'Boston', 'MA', '02120', 5, 'walnutShell606'),
(10, 10, '707 Chestnut Ter', 'Brookline', 'MA', '02445', 2, 'chestNut707');
SET IDENTITY_INSERT dbo.PROPERTY OFF;
GO

-- 4. TENANT (Lease_ID removed per feedback)
INSERT INTO dbo.TENANT (Tenant_ID, Current_Net_Balance, Emergency_Contact, Tenant_Responsibility_Score) VALUES
(11, -50.00, 'Mom: 555-9001', 95),
(12, 25.00, 'Dad: 555-9002', 88),
(13, 0.00, 'Sister: 555-9003', 100),
(14, -120.50, 'Brother: 555-9004', 70),
(15, 15.00, 'Friend: 555-9005', 92),
(16, 0.00, 'Aunt: 555-9006', 85),
(17, -30.00, 'Uncle: 555-9007', 98),
(18, 0.00, 'Mom: 555-9008', 100),
(19, 45.00, 'Dad: 555-9009', 75),
(20, -10.00, 'Sister: 555-9010', 89);
GO

-- 5. LEASE_AGREEMENT (Tenant_ID added per feedback)
SET IDENTITY_INSERT dbo.LEASE_AGREEMENT ON;
INSERT INTO dbo.LEASE_AGREEMENT (Lease_ID, Property_ID, Tenant_ID, Start_Date, End_Date, Move_In_Date, Document_URL) VALUES
(1, 1, 11, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease1.pdf'),
(2, 2, 12, '2025-09-01', '2026-08-31', '2025-09-05', 'https://cohabitant.com/lease2.pdf'),
(3, 3, 13, '2026-01-01', '2026-12-31', '2026-01-02', 'https://cohabitant.com/lease3.pdf'),
(4, 4, 14, '2025-06-01', '2026-05-31', '2025-06-01', 'https://cohabitant.com/lease4.pdf'),
(5, 5, 15, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease5.pdf'),
(6, 6, 16, '2026-02-01', '2027-01-31', '2026-02-01', 'https://cohabitant.com/lease6.pdf'),
(7, 7, 17, '2025-08-01', '2026-07-31', '2025-08-10', 'https://cohabitant.com/lease7.pdf'),
(8, 8, 18, '2025-09-01', '2026-08-31', '2025-09-02', 'https://cohabitant.com/lease8.pdf'),
(9, 9, 19, '2025-10-01', '2026-09-30', '2025-10-01', 'https://cohabitant.com/lease9.pdf'),
(10, 10, 20, '2026-01-15', '2027-01-14', '2026-01-15', 'https://cohabitant.com/lease10.pdf');
SET IDENTITY_INSERT dbo.LEASE_AGREEMENT OFF;
GO

-- 6. SUB_LEASE
SET IDENTITY_INSERT dbo.SUB_LEASE ON;
INSERT INTO dbo.SUB_LEASE (SubLease_ID, Tenant_ID, Start_Date, End_Date, Pro_Rated_Cost) VALUES
(1, 11, '2026-06-01', '2026-08-31', 1200.00),
(2, 12, '2026-05-01', '2026-08-31', 1500.00),
(3, 13, '2026-07-01', '2026-08-31', 800.00),
(4, 14, '2026-10-01', '2026-12-31', 1100.00),
(5, 15, '2026-01-01', '2026-05-31', 2000.00),
(6, 16, '2026-06-01', '2026-08-31', 1300.00),
(7, 17, '2026-11-01', '2027-01-31', 1400.00),
(8, 18, '2026-05-01', '2026-07-31', 1250.00),
(9, 19, '2026-06-01', '2026-08-31', 1150.00),
(10, 20, '2026-07-01', '2026-09-30', 1050.00);
SET IDENTITY_INSERT dbo.SUB_LEASE OFF;
GO

-- 7. GUEST
SET IDENTITY_INSERT dbo.GUEST ON;
INSERT INTO dbo.GUEST (Guest_ID, Tenant_ID, First_Name, Last_Name, Arrival_Date, Is_Overnight) VALUES
(1, 11, 'John', 'Doe', '2026-03-15', 1),
(2, 12, 'Jane', 'Smith', '2026-03-16', 0),
(3, 13, 'Mike', 'Johnson', '2026-03-17', 1),
(4, 14, 'Emily', 'Davis', '2026-03-18', 0),
(5, 15, 'Chris', 'Wilson', '2026-03-19', 1),
(6, 16, 'Sarah', 'Brown', '2026-03-20', 0),
(7, 17, 'David', 'Taylor', '2026-03-21', 1),
(8, 18, 'Jessica', 'Anderson', '2026-03-22', 0),
(9, 19, 'Matthew', 'Thomas', '2026-03-23', 1),
(10, 20, 'Ashley', 'Jackson', '2026-03-24', 0);
SET IDENTITY_INSERT dbo.GUEST OFF;
GO

-- 8. INVENTORY_ITEM 
SET IDENTITY_INSERT dbo.INVENTORY_ITEM ON;
INSERT INTO dbo.INVENTORY_ITEM (Item_ID, Item_Name, Total_Quantity, Category, Storage_Location) VALUES
(1, 'Paper Towels', 6, 'Cleaning', 'Kitchen Pantry'),
(2, 'Dish Soap', 2, 'Cleaning', 'Under Sink'),
(3, 'Toilet Paper', 12, 'Bathroom', 'Hall Closet'),
(4, 'Trash Bags', 30, 'Kitchen', 'Under Sink'),
(5, 'Olive Oil', 1, 'Groceries', 'Kitchen Cabinet'),
(6, 'Salt', 1, 'Groceries', 'Kitchen Spice Rack'),
(7, 'All-Purpose Cleaner', 2, 'Cleaning', 'Utility Closet'),
(8, 'Laundry Detergent', 1, 'Cleaning', 'Laundry Room'),
(9, 'Sponges', 4, 'Cleaning', 'Under Sink'),
(10, 'Coffee Filters', 50, 'Kitchen', 'Pantry'),
(11, 'Protein Powder', 1, 'Groceries', 'Tenant 11 Shelf'),
(12, 'Almond Milk', 2, 'Groceries', 'Fridge Top Shelf'),
(13, 'Hair Gel', 1, 'Personal Care', 'Bathroom Vanity'),
(14, 'Expensive Shampoo', 1, 'Personal Care', 'Shower Caddy'),
(15, 'Gaming Controller', 2, 'Electronics', 'Living Room'),
(16, 'Laptop Charger', 1, 'Electronics', 'Tenant 16 Room'),
(17, 'Specialty Coffee', 1, 'Groceries', 'Pantry'),
(18, 'Greek Yogurt', 4, 'Groceries', 'Fridge Bottom Shelf'),
(19, 'Toothpaste', 1, 'Personal Care', 'Bathroom Cabinet'),
(20, 'Electric Razor', 1, 'Personal Care', 'Bathroom Drawer');
SET IDENTITY_INSERT dbo.INVENTORY_ITEM OFF;
GO

-- 9. SHARED_ITEM 
INSERT INTO dbo.SHARED_ITEM (Item_ID, Property_ID, Low_Stock_Threshold, Auto_Replenish_Flag) VALUES
(1, 1, 2, 1),
(2, 1, 1, 0),
(3, 2, 4, 1),
(4, 3, 10, 0),
(5, 4, 1, 0),
(6, 5, 1, 0),
(7, 6, 1, 1),
(8, 7, 1, 1),
(9, 8, 2, 0),
(10, 9, 10, 0);
GO

-- 10. PERSONAL_ITEM 
INSERT INTO dbo.PERSONAL_ITEM (Item_ID, Tenant_ID, Is_Private) VALUES
(11, 11, 1),
(12, 12, 0),
(13, 13, 1),
(14, 14, 1),
(15, 15, 0),
(16, 16, 1),
(17, 17, 1),
(18, 18, 1),
(19, 19, 1),
(20, 20, 1);
GO

-- 11. EXPENSE
SET IDENTITY_INSERT dbo.EXPENSE ON;
INSERT INTO dbo.EXPENSE (Expense_ID, Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy, Receipt_Image) VALUES
(1, 11, 120.00, '2026-03-01', 'Equal', 'receipt_elec_mar.jpg'),
(2, 12, 45.50, '2026-03-05', 'Equal', 'receipt_groceries.jpg'),
(3, 13, 80.00, '2026-03-10', 'Custom', 'receipt_internet.jpg'),
(4, 14, 200.00, '2026-03-12', 'Equal', 'receipt_cleaning.jpg'),
(5, 15, 30.00, '2026-03-15', 'Equal', 'receipt_supplies.jpg'),
(6, 16, 150.00, '2026-03-18', 'Custom', 'receipt_gas.jpg'),
(7, 17, 60.00, '2026-03-20', 'Equal', 'receipt_water.jpg'),
(8, 18, 90.00, '2026-03-22', 'Equal', 'receipt_furniture.jpg'),
(9, 19, 25.00, '2026-03-25', 'Custom', 'receipt_streaming.jpg'),
(10, 20, 110.00, '2026-03-28', 'Equal', 'receipt_repairs.jpg');
SET IDENTITY_INSERT dbo.EXPENSE OFF;
GO

-- 12. EXPENSE_SHARE
SET IDENTITY_INSERT dbo.EXPENSE_SHARE ON;
INSERT INTO dbo.EXPENSE_SHARE (Share_ID, Expense_ID, Owed_By_Tenant_ID, Owed_Amount, Status) VALUES
(1, 1, 12, 60.00, 'Pending'),
(2, 2, 11, 22.75, 'Paid'),
(3, 3, 14, 40.00, 'Pending'),
(4, 4, 15, 100.00, 'Paid'),
(5, 5, 16, 15.00, 'Pending'),
(6, 6, 17, 75.00, 'Pending'),
(7, 7, 18, 30.00, 'Paid'),
(8, 8, 19, 45.00, 'Pending'),
(9, 9, 20, 12.50, 'Paid'),
(10, 10, 11, 55.00, 'Pending');
SET IDENTITY_INSERT dbo.EXPENSE_SHARE OFF;
GO

-- 13. PAYMENT
SET IDENTITY_INSERT dbo.PAYMENT ON;
INSERT INTO dbo.PAYMENT (Payment_ID, Payer_Tenant_ID, Amount, Payment_Date, Note) VALUES
(1, 12, 60.00, '2026-03-02', 'For March Electricity'),
(2, 11, 22.75, '2026-03-06', 'Groceries share'),
(3, 14, 40.00, '2026-03-11', 'Internet bill'),
(4, 15, 100.00, '2026-03-13', 'Deep cleaning service'),
(5, 16, 15.00, '2026-03-16', 'Paper towels and soap'),
(6, 17, 75.00, '2026-03-19', 'Gas bill'),
(7, 18, 30.00, '2026-03-21', 'Water bill'),
(8, 19, 45.00, '2026-03-23', 'Couch repair share'),
(9, 20, 12.50, '2026-03-26', 'Netflix/Hulu split'),
(10, 11, 55.00, '2026-03-29', 'Sink repair share');
SET IDENTITY_INSERT dbo.PAYMENT OFF;
GO

-- 14. CHORE_DEFINITION
SET IDENTITY_INSERT dbo.CHORE_DEFINITION ON;
INSERT INTO dbo.CHORE_DEFINITION (Chore_ID, Task_Name, Description, Difficulty_Weight, Frequency) VALUES
(1, 'Take Out Trash', 'Empty kitchen and bathroom bins to curbside.', 2, 'Weekly'),
(2, 'Clean Kitchen', 'Wipe counters, clean sink, sweep floor.', 5, 'Weekly'),
(3, 'Vacuum Living Room', 'Vacuum rug and floors in common area.', 3, 'Bi-Weekly'),
(4, 'Clean Bathroom', 'Scrub toilet, shower, and sink.', 7, 'Weekly'),
(5, 'Mop Floors', 'Mop kitchen and hardwood areas.', 4, 'Bi-Weekly'),
(6, 'Dust Furniture', 'Dust shelves and TV stand.', 2, 'Monthly'),
(7, 'Clean Fridge', 'Throw out expired food and wipe shelves.', 6, 'Monthly'),
(8, 'Organize Pantry', 'Rearrange items neatly.', 3, 'Monthly'),
(9, 'Take Out Recycling', 'Sort and take recycling bins out.', 2, 'Weekly'),
(10, 'Deep Clean Oven', 'Use oven cleaner and scrub interior.', 8, 'Quarterly');
SET IDENTITY_INSERT dbo.CHORE_DEFINITION OFF;
GO

-- 15. CHORE_ASSIGNMENT
SET IDENTITY_INSERT dbo.CHORE_ASSIGNMENT ON;
INSERT INTO dbo.CHORE_ASSIGNMENT (Assignment_ID, Chore_ID, Assigned_Tenant_ID, Due_Date, Completion_Date, Status, Proof_Image) VALUES
(1, 1, 11, '2026-03-05', '2026-03-05', 'Completed', 'trash_done.jpg'),
(2, 2, 12, '2026-03-07', NULL, 'Pending', NULL),
(3, 3, 13, '2026-03-10', '2026-03-09', 'Completed', 'vacuum_done.jpg'),
(4, 4, 14, '2026-03-12', NULL, 'Pending', NULL),
(5, 5, 15, '2026-03-15', '2026-03-15', 'Completed', 'mop_done.jpg'),
(6, 6, 16, '2026-03-20', NULL, 'Pending', NULL),
(7, 7, 17, '2026-03-25', '2026-03-24', 'Completed', 'fridge_done.jpg'),
(8, 8, 18, '2026-03-28', NULL, 'Pending', NULL),
(9, 9, 19, '2026-03-30', '2026-03-30', 'Completed', 'recycling_done.jpg'),
(10, 10, 20, '2026-04-05', NULL, 'Pending', NULL);
SET IDENTITY_INSERT dbo.CHORE_ASSIGNMENT OFF;
GO

-- 16. PROPOSAL
SET IDENTITY_INSERT dbo.PROPOSAL ON;
INSERT INTO dbo.PROPOSAL (Proposal_ID, Proposed_By_Tenant_ID, Description, Cost_Threshold, Status) VALUES
(1, 11, 'Buy a new living room rug', 150.00, 'Active'),
(2, 12, 'Implement quiet hours after 11 PM', 0.00, 'Approved'),
(3, 13, 'Upgrade internet speed', 20.00, 'Active'),
(4, 14, 'Hire bi-weekly cleaning service', 100.00, 'Rejected'),
(5, 15, 'Split cost for a shared air fryer', 80.00, 'Approved'),
(6, 16, 'Change thermostat default to 70 degrees', 0.00, 'Active'),
(7, 17, 'Get a house Netflix account', 15.00, 'Approved'),
(8, 18, 'Ban guests during finals week', 0.00, 'Rejected'),
(9, 19, 'Buy a shared printer', 120.00, 'Active'),
(10, 20, 'Start composting in the kitchen', 30.00, 'Approved');
SET IDENTITY_INSERT dbo.PROPOSAL OFF;
GO

-- 17. VOTE
SET IDENTITY_INSERT dbo.VOTE ON;
INSERT INTO dbo.VOTE (Vote_ID, Proposal_ID, Tenant_ID, Approval_Status, Vote_Timestamp) VALUES
(1, 1, 12, 1, '2026-03-01 10:00:00'),
(2, 2, 11, 1, '2026-03-02 11:30:00'),
(3, 3, 14, 0, '2026-03-03 14:15:00'),
(4, 4, 15, 0, '2026-03-04 09:45:00'),
(5, 5, 16, 1, '2026-03-05 16:20:00'),
(6, 6, 17, 1, '2026-03-06 18:05:00'),
(7, 7, 18, 1, '2026-03-07 20:10:00'),
(8, 8, 19, 0, '2026-03-08 08:55:00'),
(9, 9, 20, 1, '2026-03-09 12:40:00'),
(10, 10, 11, 1, '2026-03-10 22:15:00');
SET IDENTITY_INSERT dbo.VOTE OFF;
GO

-- 18. UTILITY_TYPE (New Lookup Table)
SET IDENTITY_INSERT dbo.UTILITY_TYPE ON;
INSERT INTO dbo.UTILITY_TYPE (Utility_Type_ID, Type_Name) VALUES
(1, 'Electricity'),
(2, 'Water'),
(3, 'Gas'),
(4, 'Internet'),
(5, 'Trash Collection'),
(6, 'Recycling'),
(7, 'Sewer'),
(8, 'Cable TV'),
(9, 'Security System'),
(10, 'Heating Oil');
SET IDENTITY_INSERT dbo.UTILITY_TYPE OFF;
GO

-- 19. UTILITY_READING (Updated to use Lookup ID)
SET IDENTITY_INSERT dbo.UTILITY_READING ON;
INSERT INTO dbo.UTILITY_READING (Reading_ID, Property_ID, Utility_Type_ID, Provider_Name, Meter_Value, Reading_Date) VALUES
(1, 1, 1, 'Eversource', 1500.50, '2026-03-01'),
(2, 2, 2, 'MWRA', 320.10, '2026-03-02'),
(3, 3, 3, 'National Grid', 850.75, '2026-03-03'),
(4, 4, 1, 'Eversource', 1420.00, '2026-03-04'),
(5, 5, 2, 'MWRA', 315.20, '2026-03-05'),
(6, 6, 3, 'National Grid', 890.30, '2026-03-06'),
(7, 7, 1, 'Eversource', 1600.80, '2026-03-07'),
(8, 8, 2, 'MWRA', 330.45, '2026-03-08'),
(9, 9, 3, 'National Grid', 810.90, '2026-03-09'),
(10, 10, 1, 'Eversource', 1380.25, '2026-03-10');
SET IDENTITY_INSERT dbo.UTILITY_READING OFF;
GO