ZLT BR Bale Tracker - TSF Mvurwi

Track unsold tobacco bales stacked vertically 3-5 high along rows at TSF Mvurwi.
Scanner posts daily → Django stores location → One-page HTMX app for search + update.

Problem
Unsold bales are stacked vertically in rows across 4 floors. 
BR staff currently spend hours walking floors to locate a specific bale for customers or collection.

Solution
Scan bale barcode → system pulls grower/lot/mass from ZLT scanner API → saves to Stack/Row/Level.
Search by grower code or date to get exact location instantly: "STACK-A-07 Row 12 Level 3".

Stack Layout
- **Floor**: A, B, C, D
- **Stack**: e.g. STACK-A-07 
- **Row**: 1-34 along the stack length
- **Level**: 1-5 vertical height, bale is placed on top of previous bale

Tech Stack
Django 5 + Django REST Framework + HTMX + SQLite/Postgres
*Project Specification Sheet*

*System Name:* ZLT BR Bale Location Tracker  
*Department:* Collection BR Dept, TSF Mvurwi  
*Owner:* ZLT  
*Season:* 2025/26

*Objective:* Maintain real-time database of unsold bale positions to reduce location time from 30min to <10sec.

*Environment:* Internal ZLT WiFi. Accessed via Android tablet + Bluetooth barcode scanner.

*Data Flow:*
1. Worker scans bale barcode on ticket
2. API calls ZLT scanner system → returns growers, lot, mass, class
3. Worker selects Stack + Row + Level on tablet
4. System saves/updates record or marks as collected
