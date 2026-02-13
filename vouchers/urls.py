from django.urls import path
from . import views

urlpatterns = [
    path('', views.voucher_list, name='voucher_list'),
    path('vouchers/edit/<int:id>/', views.edit_voucher, name='voucher_edit'),
    path('vouchers/delete/<int:id>/', views.delete_voucher, name='voucher_delete'),

]
