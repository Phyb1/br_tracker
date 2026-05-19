from django import forms
from.models import BRRecord, Bale, Floor, Side, BaleStatus, BaleReason
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Div, HTML, Submit

class BRRecordForm(forms.ModelForm):
    class Meta:
        model = BRRecord
        fields = ['br_number', 'sale_date', 'received_date', 'total_bales', 'notes']
        widgets = {
            'sale_date': forms.DateInput(attrs={'type': 'date'}),
            'received_date': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }
        help_texts = {
            'br_number': 'Unique BR number from auction floor',
            'sale_date': 'Date of auction sale',
            'received_date': 'Timestamp when bales arrived at TSF',
            'total_bales': 'Expected count from BR doc. Optional',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Div(
                Field('br_number'),
                Field('sale_date'),
                Field('received_date'),
                Field('total_bales'),
                Field('notes'),
                css_class='grid grid-2'
            )
        )

class BaleForm(forms.ModelForm):
    class Meta:
        model = Bale
        fields = [
            'br_record',
            'barcode',
            'grower_no',
            'lot_no',
            'mass',
            'reason',
            'reason_notes',
            'floor',
            'row',
            'side',
            'level',
            'status',
            'date_received'
        ]
        widgets = {
            'date_received': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reason_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Required for defects'}),
            'barcode': forms.TextInput(attrs={'placeholder': 'Scan or type barcode', 'autofocus': True}),
            'mass': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        }
        help_texts = {
            'grower_no': 'Farmer/grower ID - required',
            'lot_no': 'Lot number - required',
            'mass': 'Mass in kg - required, min 0.01kg',
            'floor': 'Warehouse floor A-D',
            'row': 'Row number in stack',
            'side': 'Left or Right side of row',
            'level': 'Vertical level. 1 = bottom level',
            'reason': 'RR=Weight, MR=Mixed, LR=Mouldy, BGRW=Wet, OR=Hot, WR=Hessian, DR=Diesel, NE=Nesting',
            'br_record': 'Link to source BR. Leave blank if unknown',
            'status': 'InStock for available bales',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only 3 fields mandatory
        self.fields['grower_no'].required = True
        self.fields['lot_no'].required = True
        self.fields['mass'].required = True

        # Everything else optional
        for field in self.fields:
            if field not in ['grower_no', 'lot_no', 'mass']:
                self.fields[field].required = False

        # Set sensible defaults
        self.fields['reason'].initial = BaleReason.GOOD
        self.fields['status'].initial = BaleStatus.IN_STOCK
        self.fields['floor'].initial = Floor.A
        self.fields['side'].initial = Side.LEFT
        self.fields['level'].initial = 1
        self.fields['row'].initial = 1

        # Crispy layout
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Div(
                Field('barcode'),
                Field('br_record'),
                css_class='grid grid-2'
            ),
            Div(
                Field('grower_no'),
                Field('lot_no'),
                Field('mass'),
                Field('reason'),
                css_class='grid grid-2'
            ),
            Field('reason_notes'),
            Div(
                Field('floor'),
                Field('row'),
                Field('side'),
                Field('level'),
                css_class='grid grid-4'
            ),
            Div(
                Field('status'),
                Field('date_received'),
                css_class='grid grid-2'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get('reason')
        reason_notes = cleaned_data.get('reason_notes')

        # Require notes for defect codes
        if reason and reason!= BaleReason.GOOD and not reason_notes:
            self.add_error('reason_notes', 'Notes required when reason is not GOOD')

        return cleaned_data

class BaleSearchForm(forms.Form):
    grower_no = forms.CharField(
        max_length=20,
        required=False,
        label='Grower No',
        help_text="Enter grower number to search"
    )
    status = forms.ChoiceField(
        choices=[('', 'All')] + list(BaleStatus.choices),
        required=False,
        label='Status',
        help_text="Filter by bale status"
    )
    floor = forms.ChoiceField(
        choices=[('', 'All')] + list(Floor.choices),
        required=False,
        label='Floor',
        help_text="Search across all floors by default"
    )
    row = forms.IntegerField(
        required=False,
        min_value=1,
        label='Row',
        help_text="Filter by row number"
    )
    side = forms.ChoiceField(
        choices=[('', 'All')] + list(Side.choices),
        required=False,
        label='Side',
        help_text="Filter by side"
    )
    level = forms.IntegerField(
        required=False,
        min_value=1,
        label='Level',
        help_text="Filter by level"
    )
    reason = forms.ChoiceField(
        choices=[('', 'All')] + list(BaleReason.choices),
        required=False,
        label='Reason',
        help_text="Filter by bale reason"
    )
    barcode = forms.CharField(
        max_length=50,
        required=False,
        label='Barcode',
        help_text="Scan or enter barcode"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.disable_csrf = True

        self.helper.layout = Layout(
            # Only grower_no visible by default
            Field('grower_no'),

            # Advanced filters toggle
            HTML('<button type="button" class="btn" id="toggle-advanced" style="background: var(--bg-secondary); color: var(--text); margin-top: 1rem; width: auto;">Advanced Filters</button>'),

            # Hidden advanced filters
            Div(
                Field('barcode'),
                Div(
                    Field('status'),
                    Field('floor'),
                    css_class='grid grid-2'
                ),
                Div(
                    Field('row'),
                    Field('side'),
                    css_class='grid grid-2'
                ),
                Div(
                    Field('level'),
                    Field('reason'),
                    css_class='grid grid-2'
                ),
                css_class='advanced-filters hidden',
                id='advanced-filters'
            ),

            # Submit button
            Div(
                Submit('submit', 'Search', css_class='btn'),
                css_class='form-actions',
                style='margin-top: 1.5rem;'
            )
        )
