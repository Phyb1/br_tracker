
*Functional Requirements*

*1. Data Model*
Entity	Field	Type	Description
**Stack**	code	Char	Unique stack ID e.g. STACK-A-07
	floor	Char	A,B,C,D
**Bale**	barcode	Char	Unique bale ID from ticket
	stack	FK	Reference to Stack
	row	Int	1-34, position along stack length
	level	Int	1-5, vertical height in stack
	growers	Char	Grower code, letters only e.g. ABC
	lot	Char	Lot number, integers with dash e.g. 123-45
	mass	Decimal	Mass in kg from scanner API
	bale_class	Char	RR, MR, LR, BGRW, WR
	status	Char	unsold, collected
	season	Date	Season start date e.g. 2025-07-01
	recorded_date	Date	Date bale was stacked
	collected_date	Date	Date bale was removed
*Business Rules:*
- Unique constraint: `stack + row + level` = one bale slot only
- Level 1 is ground level, Level 5 is top. Cannot have Level 3 without Level 1-2 existing
- One barcode = one active record. Re-scanning moves bale to new location

*2. Class Definitions*
- *RR*: Overweight or underweight
- *MR*: Mixed hands  
- *LR*: Moldy
- *BGRW*: Wet
- *WR*: Foreign matter

*3. REST API Endpoints*

*POST /api/bale/scan/*
Records or updates bale location after scan.
Request:
{
  "barcode": "TSF202512345",
  "stack_code": "STACK-A-07",
  "row": 12,
  "level": 3,
  "season": "2025-07-01"
}

Response:
{
  "status": "success",
  "action": "created",
  "location": "STACK-A-07 Row 12 Level 3",
  "growers": "ABC",
  "lot": "123-45",
  "mass": "85.50",
  "bale_class": "RR"
}
*POST /api/bale/collect/{id}/*
Marks bale as collected and sets collected_date to today.

*GET /api/bale/search/?growers=ABC&date=2025-09-01*
Returns list of unsold bales matching filters.

*4. One-Page Web Application*

*Tab 1: Record*
- Barcode input with autofocus for scanner
- Stack dropdown, Row input 1-34, Level input 1-5
- Submit via HTMX, no page reload
- Success shows green confirmation with full location

*Tab 2: Search*  
- Search by growers code or recorded date
- Results show: Barcode, Location, Growers, Lot, Class, Mass, Date
- "Mark Collected" button per row

*Tab 3: Daily Report*
- Table of all unsold bales recorded today
- Export to CSV button
- Filter by floor

*5. Validation Rules*
- Row must be 1-34
- Level must be 1-5
- Level validation: If Level 3 is selected, Level 1 and 2 must already have bales in that row
- Barcode must exist in ZLT scanner API before saving

*6. User Roles*
- *BR Clerk*: Record bales, search bales, mark collected
- *BR Supervisor*: View daily report, export CSV
