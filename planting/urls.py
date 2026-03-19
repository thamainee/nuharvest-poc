from django.urls import path
from . import views
from django.contrib import admin

urlpatterns = [
    path('',                              views.dashboard,              name='dashboard'),
    path('login/',                        views.login_view,             name='login'),
    path('logout/',                       views.logout_view,            name='logout'),
    path('upload/',                       views.upload_file,            name='upload_file'),
    path('upload/process/',               views.upload_process,         name='upload_process'),
    path('upload/result/<int:batch_id>/', views.upload_result,          name='upload_result'),
    path('upload/import/<int:batch_id>/', views.import_batch,           name='import_batch'),
    path('notifications/',                views.notifications_page,     name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_read'),
    path('notifications/mark-all-read/', views.mark_all_read,           name='mark_all_read'),
    path('notifications/check/',         views.check_alerts,            name='check_alerts'),
    path('notifications/send-email/',    views.send_alert_email_view,   name='send_alert_email'),
    path('load-initial-data/',           views.load_initial_data,       name='load_initial_data'),
    path('upload/manage/',               views.manage_uploads,          name='manage_uploads'),
    path('upload/delete/<int:batch_id>/',views.delete_batch,            name='delete_batch'),
    path('upload/reupload/<int:batch_id>/',views.reupload_batch,        name='reupload_batch'),
    path("admin/", admin.site.urls),
]
