from django.urls import path
from . import views

urlpatterns = [
    path('', views.voucher_list, name='voucher_list'),
    path('vouchers/edit/<int:id>/', views.edit_voucher, name='voucher_edit'),
    path('vouchers/delete/<int:id>/', views.delete_voucher, name='voucher_delete'),
    path('batches/delete/<int:id>/', views.delete_voucher_batch, name='voucher_batch_delete'),
    path('generate/', views.generate_vouchers, name='voucher_generate'),
    path('batches/<int:batch_id>/download/', views.download_batch_csv, name='voucher_batch_download'),
]
