from django import forms
from .models import BRRecord, Bale, Floor, Side, BaleStatus, BaleReason

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
    status = forms.ChoiceField(choices=[('', 'All')] + list(BaleStatus.choices), required=False)
    floor = forms.ChoiceField(choices=[('', 'All')] + list(Floor.choices), required=False)
    reason = forms.ChoiceField(choices=[('', 'All')] + list(BaleReason.choices), required=False)
    grower_no = forms.CharField(max_length=20, required=False)
    barcode = forms.CharField(max_length=50, required=False)
