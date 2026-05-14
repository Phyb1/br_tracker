"""
Views for the BR Bale Tracker app.

All views use CBVs with mixins for permissions and HTMX partial rendering.
Login required for all views. BR Clerk and Collection Dept permissions enforced via mixins.
"""
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, View, TemplateView

from .forms import BRRecordForm, BaleForm, BaleSearchForm
from .models import Bale, BRRecord

class BRClerkRequiredMixin(UserPassesTestMixin):
    """Allow access only to users in the BR Clerk group."""
    
    def test_func(self):
        return self.request.user.groups.filter(name='BR Clerk').exists()
    
    def handle_no_permission(self):
        return HttpResponse("Forbidden: BR Clerk access required", status=403)

class CollectionDeptRequiredMixin(UserPassesTestMixin):
    """Allow access only to users in the Collection Dept group."""
    
    def test_func(self):
        return self.request.user.groups.filter(name='Collection Dept').exists()
    
    def handle_no_permission(self):
        return HttpResponse("Forbidden: Collection Dept access required", status=403)

class BaleListView(LoginRequiredMixin, ListView):
    """
    Display a filterable, paginated list of bales.
    
    Supports HTMX partial rendering for live search and filtering.
    """
    model = Bale
    template_name = 'tracker/bale_list.html'
    context_object_name = 'bales'
    paginate_by = 50

    def get_queryset(self):
        qs = Bale.objects.select_related(
            'br_record', 'scanned_by', 'collected_by'
        ).order_by('-date_scanned')
        
        form = BaleSearchForm(self.request.GET)
        if form.is_valid():
            for field in ['status', 'floor', 'reason', 'grower_no', 'barcode']:
                val = form.cleaned_data.get(field)
                if val:
                    lookup = f"{field}__icontains" if field in ['grower_no', 'barcode'] else field
                    qs = qs.filter(**{lookup: val})
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = BaleSearchForm(self.request.GET)
        context['is_br_clerk'] = self.request.user.groups.filter(name='BR Clerk').exists()
        context['is_collection'] = self.request.user.groups.filter(name='Collection Dept').exists()
        return context

    def render_to_response(self, context):
        """Render partial template for HTMX requests."""
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'tracker/partials/bale_table.html', context)
        return super().render_to_response(context)

class BaleDetailView(LoginRequiredMixin, DetailView):
    """Display detailed view of a single bale including history."""
    model = Bale
    template_name = 'tracker/bale_detail.html'
    queryset = Bale.objects.select_related('br_record', 'scanned_by', 'collected_by')

class BaleCreateView(LoginRequiredMixin, BRClerkRequiredMixin, CreateView):
    """Create a new bale record. BR Clerk only."""
    model = Bale
    form_class = BaleForm
    template_name = 'tracker/bale_form.html'

    def form_valid(self, form):
        form.instance.scanned_by = self.request.user
        return super().form_valid(form)

    def get_initial(self):
        """Pre-fill br_record if coming from BR detail page."""
        initial = super().get_initial()
        br_id = self.kwargs.get('br_id')
        if br_id:
            initial['br_record'] = br_id
        return initial

class BRRecordListView(LoginRequiredMixin, ListView):
    """List all BR records with pagination."""
    model = BRRecord
    template_name = 'tracker/brrecord_list.html'
    paginate_by = 20
    ordering = ['-sale_date']

class BRRecordCreateView(LoginRequiredMixin, BRClerkRequiredMixin, CreateView):
    """Create a new BR record. BR Clerk only."""
    model = BRRecord
    form_class = BRRecordForm
    template_name = 'tracker/brrecord_form.html'
    success_url = reverse_lazy('tracker:brrecord_list')

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)

class BaleReserveView(LoginRequiredMixin, CollectionDeptRequiredMixin, View):
    """Mark a bale as reserved for collection. Collection Dept only."""
    
    def post(self, request, pk):
        bale = get_object_or_404(Bale, pk=pk)
        bale.reserve_for_collection(request.user)
        return render(request, 'tracker/partials/bale_row.html', {'bale': bale})

class BaleCollectView(LoginRequiredMixin, CollectionDeptRequiredMixin, View):
    """Mark a bale as collected. Collection Dept only."""
    
    def post(self, request, pk):
        bale = get_object_or_404(Bale, pk=pk)
        bale.mark_collected(request.user)
        return render(request, 'tracker/partials/bale_row.html', {'bale': bale})

class MetricsDashboardView(LoginRequiredMixin, TemplateView):
    """Display intake, collection, and defect metrics for a date range."""
    template_name = 'tracker/metrics_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        end_date = self.request.GET.get('end', timezone.now().date())
        start_date = self.request.GET.get('start', end_date - timedelta(days=7))

        metrics = Bale.objects.in_out_ratio(start_date, end_date)
        defects = (
            Bale.objects.defects()
            .filter(date_scanned__date__range=[start_date, end_date])
            .values('reason')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        stock_by_floor = (
            Bale.objects.in_stock()
            .values('floor')
            .annotate(count=Count('id'))
        )

        context.update({
            'metrics': metrics,
            'defects': defects,
            'stock_by_floor': stock_by_floor,
            'start_date': start_date,
            'end_date': end_date,
        })
        return context
