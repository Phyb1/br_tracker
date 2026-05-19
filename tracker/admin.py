"""
Django admin configuration for BR Bale Tracker.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Bale, BRRecord, BaleHistory

# --- Branding ---
admin.site_header = "TSF Mvurwi - Bale Management"
admin.site_title = "TSF Mvurwi Admin"
admin.site.index_title = "Dashboard"

@admin.register(BRRecord)
class BRRecordAdmin(admin.ModelAdmin):
    list_display = ['br_number', 'sale_date', 'total_bales', 'total_mass', 'recorded_by']
    list_filter = ['sale_date']
    search_fields = ['br_number']
    readonly_fields = ['recorded_by', 'created_at']
    ordering = ['-sale_date']
    date_hierarchy = 'sale_date'
    list_per_page = 30
    
    fieldsets = (
        ('BR Details', {
            'fields': ('br_number', 'sale_date', 'received_date', 'recorded_by')
        }),
        ('Counts', {
            'fields': ('total_bales', 'total_mass', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # only set on create
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Bale)
class BaleAdmin(admin.ModelAdmin):
    list_display = [
        'barcode', 'grower_no', 'lot_no', 'mass', 
        'location_display', 'status', 'reason', 
        'scanned_by', 'date_scanned'
    ]
    list_filter = ['status', 'reason', 'floor', 'side', 'date_scanned']
    search_fields = ['barcode', 'grower_no', 'lot_no']
    readonly_fields = ['date_scanned', 'date_collected', 'scanned_by', 'collected_by']
    ordering = ['floor', 'row', 'side', 'level']
    list_per_page = 50
    list_select_related = ['br_record', 'scanned_by', 'collected_by']
    list_editable = ['status', 'reason']  # quick inline edits
    
    fieldsets = (
        ('Identification - Required', {
            'fields': ('grower_no', 'lot_no', 'mass'),
            'description': 'Only these 3 fields are mandatory'
        }),
        ('Identification - Optional', {
            'fields': ('br_record', 'barcode'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('floor', 'row', 'side', 'level'),
            'description': 'Location is identified by Floor + Row + Side + Level'
        }),
        ('Status & Quality', {
            'fields': ('status', 'reason', 'reason_notes', 'date_collected')
        }),
        ('Audit', {
            'fields': ('scanned_by', 'collected_by', 'date_scanned'),
            'classes': ('collapse',)
        }),
    )
    
    def location_display(self, obj):
        return obj.location_display
    location_display.short_description = 'Location'
    location_display.admin_order_field = 'floor'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'br_record', 'scanned_by', 'collected_by'
        )

@admin.register(BaleHistory)
class BaleHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'bale_link', 'changed_at', 'changed_by', 
        'old_status', 'new_status', 'old_location', 'new_location'
    ]
    list_filter = ['changed_at', 'old_status', 'new_status']
    search_fields = ['bale__barcode', 'bale__grower_no', 'notes']
    readonly_fields = [f.name for f in BaleHistory._meta.fields]
    ordering = ['-changed_at']
    date_hierarchy = 'changed_at'
    list_per_page = 100
    list_select_related = ['bale', 'changed_by']
    
    def bale_link(self, obj):
        url = f'/admin/tracker/bale/{obj.bale_id}/change/'
        return format_html('<a href="{}">{}</a>', url, obj.bale.barcode or f'Bale #{obj.bale_id}')
    bale_link.short_description = 'Bale'
    
    def has_add_permission(self, request):
        return False  # History is created via signals only
    
    def has_change_permission(self, request, obj=None):
        return False  # History is immutable
    def has_delete_permission(self, request, obj=None):
        return False

