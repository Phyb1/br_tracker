# ZLT BR Bale Tracker - TSF Mvurwi

Track uncollected tobacco bales stacked vertically 3-5 high along rows at TSF Mvurwi.
v1: Manual entry via Django Admin. v2: Phone camera OCR. v3: Bluetooth scanner API.

## Problem
Uncollected bales are stacked vertically in rows across 4 floors A-D.
BR staff spend 20-30min walking floors to locate specific bales for collection/dispatch.

## Solution
Manual entry v1 → Phone OCR v2 → Full API v3. 
Search by Grower No/Lot No/Date → exact location: "FLOOR-D STACK-D-07 Row 12 Level 4"
Target: <10sec lookup vs 30min walk.

## Stack Layout
- **Floor**: A, B, C, D
- **Stack**: e.g. STACK-D-07, STACK-A-23
- **Row**: 1-34 along stack length  
- **Level**: 1-5 vertical height. Bale placed on top of previous bale

## Bale Status
- **Uncollected**: In warehouse, awaiting grower collection/dispatch
- **Collected**: Handed to grower/transporter, removed from stack

## Tech Stack
Django 5 + DRF + HTMX + SQLite/Postgres
v2 add: Tesseract OCR + OpenCV for ticket reading

## Roadmap

### v1: Manual Entry via Admin - Ship Now
1. BR staff login to `/admin/` on tablet
2. Add Bale: enter Barcode, Grower No, Lot No, Mass, Class
3. Select Floor/Stack/Row/Level from dropdowns
4. Status defaults to `Uncollected`
5. HTMX search: `/bales/` filter by Grower/Lot/Date → shows location
6. Mark `Collected` button: logs timestamp + user

### v2: Phone Camera + OCR - Next 2 Weeks
1. Worker hits `/scan/` on phone browser
2. Camera snaps bale ticket image
3. Tesseract extracts: Barcode, Grower No, Lot No, Mass
4. Form pre-filled. Worker selects Floor/Stack/Row/Level only
5. Submit → Save. OCR confidence shown. Manual override if <80%

### v3: ZLT Scanner API - Season End
1. Bluetooth barcode scanner → POST `/api/scan/`
2. Backend calls ZLT API → returns all bale data
3. Worker only picks location. Zero typing.
