"""
URL configuration for tracker app.

Routes grouped by resource. All views are class-based.
"""
from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    # Bale listing and search
    path('', views.BaleListView.as_view(), name='bale_list'),
    path('bale/<int:pk>/', views.BaleDetailView.as_view(), name='bale_detail'),
    
    # Bale actions
    path('bale/add/', views.BaleCreateView.as_view(), name='bale_create'),
    path('br/<int:br_id>/bale/add/', views.BaleCreateView.as_view(), name='bale_create_for_br'),
    path('bale/<int:pk>/reserve/', views.BaleReserveView.as_view(), name='bale_reserve'),
    path('bale/<int:pk>/collect/', views.BaleCollectView.as_view(), name='bale_collect'),
    
    # BR records
    path('br/', views.BRRecordListView.as_view(), name='brrecord_list'),
    path('br/add/', views.BRRecordCreateView.as_view(), name='brrecord_create'),
    
    # Dashboard
    path('metrics/', views.MetricsDashboardView.as_view(), name='metrics'),
]
