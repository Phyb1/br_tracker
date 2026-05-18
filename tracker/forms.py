from django import forms
from .models import BRRecord, Bale, Floor, Side, BaleStatus, BaleReason
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Div, HTML, Submit

class BRRecordForm(forms.ModelForm):
    class Meta:
        model = BRRecord
        fields = ['br_number', 'sale_date', 'received_date', 'total_bales', 'total_mass', 'notes']
        widgets = {'sale_date': forms.DateInput(attrs={'type': 'date'}), 'received_date': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

class BaleForm(forms.ModelForm):
    class Meta:
        model = Bale
        fields = ['br_record', 'barcode', 'grower_no', 'lot_no', 'mass', 'reason', 'floor', 'stack', 'row', 'side', 'level', 'date_received']
        widgets = {'date_received': forms.DateTimeInput(attrs={'type': 'datetime-local'})}



class BaleSearchForm(forms.Form):
    grower_no = forms.CharField(
        max_length=20, 
        required=False,
        help_text="Enter grower number to search"
    )
    status = forms.ChoiceField(
        choices=[('', 'All')] + list(BaleStatus.choices), 
        required=False,
        help_text="Filter by bale status"
    )
    floor = forms.ChoiceField(
        choices=[('', 'All')] + list(Floor.choices), 
        required=False,
        help_text="Search across all floors by default"
    )
    reason = forms.ChoiceField(
        choices=[('', 'All')] + list(BaleReason.choices), 
        required=False,
        help_text="Filter by bale reason"
    )
    barcode = forms.CharField(
        max_length=50, 
        required=False,
        help_text="Scan or enter barcode"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_attr = {
            'hx-get': '/tracker/bales/',  # use {% url %} in template instead
            'hx-target': '#bale-table-body',
            'hx-swap': 'innerHTML'
        }
        self.helper.layout = Layout(
            # Always visible
            Div(
                Field('grower_no', css_class='input'),
                css_class='grid-col-1'
            ),
            
            # Toggleable advanced fields
            Div(
                Div(Field('status'), Field('floor'), css_class='grid grid-2'),
                Div(Field('reason'), Field('barcode'), css_class='grid grid-2'),
                css_class='advanced-filters hidden',
                id='advanced-filters'
            ),
            
            # Buttons
            Div(
                Submit('submit', 'Search', css_class='btn btn-primary'),
                HTML('<button type="button" class="btn btn-ghost" id="toggle-advanced">Search by Other</button>'),
                css_class='form-actions'
            )
        )
