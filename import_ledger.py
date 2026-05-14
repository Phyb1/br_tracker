import os
import re
import django
import pandas as pd
from PIL import Image
import pytesseract

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'br_tracker.settings') # change to your settings module
django.setup()

from tracker.models import Bale, BRRecord
from django.contrib.auth import get_user_model

IMAGE_PATH = 'ledger.jpg' # path to your image
DEFAULT_USER = 'admin' # user to set as scanned_by

def clean_text(text):
    """OCR cleanup for the table"""
    lines = text.split('\n')
    data = []
    last_date = None
    last_grower = None
    last_lot = None
    last_loc = None
    last_reason = None

    for line in lines:
        line = line.strip()
        if not line or 'Datu' in line or 'Grower' in line:
            continue

        # Split by multiple spaces or | or tabs
        parts = re.split(r'\s{2,}|\|', line)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) < 5:
            continue

        # Handle date in first column
        date = parts[0]
        if '/' in date and len(date) >= 5:
            last_date = date
        else:
            parts = [last_date] + parts # prepend last date

        # Handle " same as above
        grower = parts[1] if parts[1]!= '"' else last_grower
        lot = parts[2] if parts[2]!= '"' else last_lot
        mass = parts[3]
        loc = parts[4] if parts[4]!= '"' else last_loc
        reason = parts[5] if len(parts) > 5 and parts[5]!= '"' else last_reason

        last_grower, last_lot, last_loc, last_reason = grower, lot, loc, reason

        data.append({
            'date': last_date,
            'grower_no': grower,
            'lot_no': lot,
            'mass': mass,
            'location': loc,
            'reason': reason
        })

    return pd.DataFrame(data)

def parse_location(loc_str):
    """Parse '28B 2R' into floor, stack, row, side"""
    if not loc_str:
        return {}, {}

    m = re.match(r'(\d+)([A-Z])\s*(\d+)([A-Z]{1,2})?', loc_str)
    if m:
        return {
            'floor': m.group(1),
            'stack': m.group(1) + m.group(2),
            'row': m.group(3),
            'side': m.group(4) or ''
        }, {}
    return {}, {}

def main():
    img = Image.open(IMAGE_PATH)
    text = pytesseract.image_to_string(img, lang='eng')

    df = clean_text(text)
    print(f"Parsed {len(df)} rows")
    print(df.head())

    user = get_user_model().objects.get(username=DEFAULT_USER)

    bales_to_create = []
    for _, row in df.iterrows():
        try:
            # Try to link to BRRecord if it exists
            br = BRRecord.objects.filter(br_number=row['grower_no']).first()

            loc_data = parse_location(row['location'])[0]

            bale = Bale(
                br_record=br,
                grower_no=row['grower_no'],
                lot_no=row['lot_no'],
                mass=float(row['mass']),
                floor=loc_data.get('floor', ''),
                stack=loc_data.get('stack', ''),
                row=loc_data.get('row', ''),
                side=loc_data.get('side', ''),
                reason=row['reason'] or 'IN_STOCK',
                status='IN_STOCK',
                scanned_by=user
            )
            bales_to_create.append(bale)
        except Exception as e:
            print(f"Skipping row {row.to_dict()} due to error: {e}")

    Bale.objects.bulk_create(bales_to_create, batch_size=100)
    print(f"Created {len(bales_to_create)} bales")

if __name__ == '__main__':
    main()
