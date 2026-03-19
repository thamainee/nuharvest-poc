import os, tempfile, json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone

from .kpi_reader import get_dashboard_data, load_excel_to_db
from .validator import validate_excel, FIELD_SCHEMA, COMPOSITE_UNIQUE_KEYS
from .models import (Department, UserProfile, WeeklyPlanting,
                     Notification, UploadBatch, ValidationError, StagingRecord)


def _get_user_dept(request):
    """Returns the user's department, or None if admin/all-access."""
    try:
        profile = request.user.profile
        if profile.can_view_all_departments or profile.role == "admin":
            return None
        return profile.department
    except Exception:
        return None


def _get_unread_notifications(request):
    dept = _get_user_dept(request)
    qs   = Notification.objects.filter(is_read=False)
    if dept:
        qs = qs.filter(department=dept)
    return qs.order_by("-created_at")[:20]


# ── Login ─────────────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = None
    if request.method == "POST":
        u = authenticate(request, username=request.POST.get("username"),
                                  password=request.POST.get("password"))
        if u:
            login(request, u)
            return redirect(request.GET.get("next", "/"))
        error = "Invalid username or password."
    return render(request, "planting/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")


# ── Dashboard ─────────────────────────────────────────────────────────────────
@login_required
def dashboard(request):
    dept   = _get_user_dept(request)
    season = request.GET.get("season")
    data   = get_dashboard_data(department=dept, season=season)
    notifs = _get_unread_notifications(request)

    # Auto-create notifications for RED and ORANGE alerts (once per day per KPI+field)
    for alert in data["alerts"]:
        if alert["severity"] not in ("RED", "ORANGE"):
            continue
        already_exists = Notification.objects.filter(
            title=alert["title"],
            kpi_name=alert.get("kpi", ""),
            field_name=alert.get("field", ""),
            created_at__date=timezone.now().date(),
        ).exists()
        if not already_exists:
            Notification.objects.create(
                department=dept,
                title=alert["title"],
                message=alert["message"],
                severity="critical" if alert["severity"] == "RED" else "warning",
                field_name=alert.get("field", ""),
                kpi_name=alert.get("kpi", ""),
                kpi_value=alert.get("value", ""),
            )

    return render(request, "planting/dashboard.html", {
        **data,
        "notifications":     notifs,
        "unread_count":      notifs.count(),
        "active_page":       "dashboard",
        "cost_trend_json":   json.dumps(data["cost_trend"]),
        "week_labels_json":  json.dumps(data["week_labels"]),
        "field_names_json":  json.dumps(data["field_names"]),
        "bar_labels_json":   json.dumps(data["bar_labels"]),
        "bar_targets_json":  json.dumps(data["bar_targets"]),
        "bar_actuals_json":  json.dumps(data["bar_actuals"]),
    })


# ── Notifications API ─────────────────────────────────────────────────────────
@login_required
def mark_notification_read(request, notif_id):
    if request.method == "POST":
        n = get_object_or_404(Notification, id=notif_id)
        n.is_read = True
        n.save()
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "POST only"}, status=405)


@login_required
def mark_all_read(request):
    if request.method == "POST":
        dept = _get_user_dept(request)
        qs   = Notification.objects.filter(is_read=False)
        if dept: qs = qs.filter(department=dept)
        qs.update(is_read=True)
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "POST only"}, status=405)


@login_required
def notifications_page(request):
    dept  = _get_user_dept(request)
    qs    = Notification.objects.all()
    if dept: qs = qs.filter(department=dept)
    notifs = _get_unread_notifications(request)
    return render(request, "planting/notifications.html", {
        "all_notifications": qs.order_by("-created_at")[:100],
        "notifications": notifs,
        "unread_count": notifs.count(),
        "active_page": "notifications",
    })


# ── Upload ────────────────────────────────────────────────────────────────────
@login_required
def upload_file(request):
    try:
        profile = request.user.profile
        if not (profile.can_upload or profile.role in ("admin", "manager")):
            messages.error(request, "You don't have permission to upload files.")
            return redirect("dashboard")
    except Exception:
        pass

    dept   = _get_user_dept(request)
    notifs = _get_unread_notifications(request)
    recent = UploadBatch.objects.order_by("-uploaded_at")
    if dept: recent = recent.filter(department=dept)
    recent = recent[:10]

    # Handle POST inline — validate and either show errors or redirect to import
    validation_errors = []
    uploaded_filename = None
    batch_id_ready    = None

    if request.method == "POST" and "excel_file" in request.FILES:
        f = request.FILES["excel_file"]
        uploaded_filename = f.name

        if not f.name.endswith((".xlsx", ".xls")):
            validation_errors = [{"message": "File must be an Excel file (.xlsx or .xls). Please select the correct file type."}]
        else:
            suffix = os.path.splitext(f.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in f.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            errors, clean_rows, headers = validate_excel(tmp_path)
            os.unlink(tmp_path)

            # Save batch regardless
            batch = UploadBatch.objects.create(
                department=dept,
                uploaded_by=request.user,
                filename=f.name,
                status="errors" if errors else "validated",
                row_count=len(clean_rows) if not errors else 0,
            )
            for e in errors:
                ValidationError.objects.create(
                    batch=batch, row_number=e.get("row"),
                    field_name=e.get("field") or "",
                    error_type=e["error_type"], message=e["message"],
                )
            if clean_rows:
                for row in clean_rows:
                    StagingRecord.objects.create(
                        batch=batch, row_number=row["row_number"],
                        week_number=str(row["week_number"]), week_label=row["week_label"],
                        season=row["season"], field_id=row["field_id"],
                        field_name=row["field_name"], block=row["block"], crop=row["crop"],
                        planned_date=str(row["planned_date"]) if row["planned_date"] else "",
                        actual_date=str(row["actual_date"])   if row["actual_date"]  else "",
                        labor_cost=str(row["labor_cost"]), qty_planted=str(row["qty_planted"]),
                        target_qty=str(row["target_qty"]), notes=row["notes"],
                    )

            if errors:
                # Stay on upload page, show errors inline
                validation_errors = errors
            else:
                # All good — redirect to import confirmation
                return redirect("upload_result", batch_id=batch.id)

        # Refresh recent after potential new batch
        recent = UploadBatch.objects.order_by("-uploaded_at")
        if dept: recent = recent.filter(department=dept)
        recent = recent[:10]

    return render(request, "planting/upload.html", {
        "recent_batches":    recent,
        "notifications":     notifs,
        "unread_count":      notifs.count(),
        "active_page":       "upload",
        "validation_errors": validation_errors,
        "uploaded_filename": uploaded_filename,
    })


@login_required
def upload_process(request):
    # This view is no longer used — upload_file handles POST directly
    return redirect("upload_file")


@login_required
def upload_result(request, batch_id):
    batch   = get_object_or_404(UploadBatch, id=batch_id)
    errors  = batch.errors.all().order_by("row_number")
    staging = batch.rows.all().order_by("row_number")
    error_types = {}
    for e in errors:
        error_types[e.error_type] = error_types.get(e.error_type, 0) + 1
    notifs = _get_unread_notifications(request)
    return render(request, "planting/upload_result.html", {
        "batch": batch, "errors": errors, "error_types": error_types,
        "staging": staging, "notifications": notifs, "unread_count": notifs.count(),
        "active_page": "upload",
    })


@login_required
def import_batch(request, batch_id):
    if request.method != "POST":
        return redirect("upload_result", batch_id=batch_id)
    batch = get_object_or_404(UploadBatch, id=batch_id)
    if batch.status != "validated":
        messages.error(request, "Only validated batches can be imported.")
        return redirect("upload_result", batch_id=batch_id)

    dept = _get_user_dept(request)
    if dept is None:
        try:
            dept = Department.objects.first()
        except: pass

    imported = skipped = 0
    for row in batch.rows.all():
        _, created = WeeklyPlanting.objects.update_or_create(
            week_number=int(row.week_number), season=row.season, field_id_ref=row.field_id,
            defaults={
                "department": dept, "week_label": row.week_label,
                "field_name": row.field_name, "block": row.block, "crop": row.crop,
                "planned_date": row.planned_date or None,
                "actual_date":  row.actual_date  or None,
                "labor_cost": float(row.labor_cost), "qty_planted": int(row.qty_planted),
                "target_qty": int(row.target_qty), "notes": row.notes,
            }
        )
        if created: imported += 1
        else: skipped += 1

    batch.status = "imported"
    batch.save()
    messages.success(request, f"✅ Import complete: {imported} new records, {skipped} updated.")
    return redirect("upload_result", batch_id=batch_id)


# ── Manage Uploads ────────────────────────────────────────────────────────────
@login_required
def manage_uploads(request):
    """List all upload batches with view / delete actions."""
    try:
        profile = request.user.profile
        if not (profile.can_upload or profile.role in ("admin", "manager")):
            messages.error(request, "You don't have permission to manage uploads.")
            return redirect("dashboard")
    except Exception:
        pass

    dept   = _get_user_dept(request)
    notifs = _get_unread_notifications(request)
    qs     = UploadBatch.objects.order_by("-uploaded_at")
    if dept:
        qs = qs.filter(department=dept)

    # Annotate each batch with its record count in the live DB
    batches = []
    for b in qs:
        live_count = 0
        if b.status == "imported":
            # count WeeklyPlanting rows that came from this batch's staging rows
            field_ids  = b.rows.values_list("field_id",    flat=True).distinct()
            week_nums  = b.rows.values_list("week_number", flat=True).distinct()
            seasons    = b.rows.values_list("season",      flat=True).distinct()
            live_count = WeeklyPlanting.objects.filter(
                field_id_ref__in=field_ids,
                week_number__in=[int(w) for w in week_nums if w],
                season__in=seasons,
            ).count()
        batches.append({
            "batch":      b,
            "live_count": live_count,
            "has_live":   b.status == "imported" and live_count > 0,
        })

    return render(request, "planting/manage_uploads.html", {
        "batches":     batches,
        "notifications": notifs,
        "unread_count":  notifs.count(),
        "active_page": "manage",
    })


@login_required
def delete_batch(request, batch_id):
    """Delete a batch and optionally its imported live records."""
    if request.method != "POST":
        return redirect("manage_uploads")

    batch       = get_object_or_404(UploadBatch, id=batch_id)
    delete_live = request.POST.get("delete_live") == "yes"
    filename    = batch.filename

    if delete_live and batch.status == "imported":
        # Remove WeeklyPlanting rows that match this batch's staging data
        deleted_live = 0
        for row in batch.rows.all():
            deleted, _ = WeeklyPlanting.objects.filter(
                field_id_ref=row.field_id,
                week_number=int(row.week_number) if row.week_number else 0,
                season=row.season,
            ).delete()
            deleted_live += deleted
        messages.success(
            request,
            f"🗑 '{filename}' deleted along with {deleted_live} live planting record(s)."
        )
    else:
        messages.success(request, f"🗑 Upload record '{filename}' removed (live data kept).")

    # Always delete the batch + its staging rows + validation errors
    batch.delete()
    return redirect("manage_uploads")


@login_required
def reupload_batch(request, batch_id):
    """Mark a batch as superseded so user knows to re-upload corrected file."""
    batch = get_object_or_404(UploadBatch, id=batch_id)
    # Just redirect to upload page — the new upload will update_or_create the records
    messages.info(
        request,
        f"Upload a corrected file to update the records from '{batch.filename}'. "
        "Matching rows (same week + season + field) will be overwritten."
    )
    return redirect("upload_file")


# ── Manual alert check ───────────────────────────────────────────────────────
@login_required
def check_alerts(request):
    """Manually re-run KPI threshold checks and create any new notifications."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    dept = _get_user_dept(request)
    data = get_dashboard_data(department=dept)
    created = 0

    for alert in data["alerts"]:
        if alert["severity"] not in ("RED", "ORANGE"):
            continue
        already_exists = Notification.objects.filter(
            title=alert["title"],
            kpi_name=alert.get("kpi", ""),
            field_name=alert.get("field", ""),
            created_at__date=timezone.now().date(),
        ).exists()
        if not already_exists:
            Notification.objects.create(
                department=dept,
                title=alert["title"],
                message=alert["message"],
                severity="critical" if alert["severity"] == "RED" else "warning",
                field_name=alert.get("field", ""),
                kpi_name=alert.get("kpi", ""),
                kpi_value=alert.get("value", ""),
            )
            created += 1

    return JsonResponse({
        "created": created,
        "total_alerts": len(data["alerts"]),
        "red_count":    sum(1 for a in data["alerts"] if a["severity"] == "RED"),
        "orange_count": sum(1 for a in data["alerts"] if a["severity"] == "ORANGE"),
    })


@login_required
def send_alert_email_view(request):
    """Send an email summary of current KPI alerts."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    dept = _get_user_dept(request)
    data = get_dashboard_data(department=dept)
    alerts = data["alerts"]

    if not alerts:
        return JsonResponse({"sent": False, "reason": "No alerts to send"})

    try:
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        recipients = getattr(settings, "ALERT_EMAIL_RECIPIENTS", [])
        if not recipients:
            return JsonResponse({"sent": False, "reason": "No recipients configured in settings.py"})

        rows_html = ""
        for a in alerts:
            colour = a["colour"]
            rows_html += f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #eee">{a['field']}</td>
              <td style="padding:10px;border-bottom:1px solid #eee">{a['kpi']}</td>
              <td style="padding:10px;border-bottom:1px solid #eee;color:{colour};font-weight:700">{a['severity']}</td>
              <td style="padding:10px;border-bottom:1px solid #eee">{a['message']}</td>
            </tr>"""

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
          <div style="background:#1B4332;padding:20px;border-radius:8px 8px 0 0">
            <h2 style="color:#fff;margin:0">🌱 NuHarvest — KPI Alert</h2>
            <p style="color:#95D5B2;margin:4px 0 0">{timezone.now().strftime('%A, %d %B %Y')}</p>
          </div>
          <div style="background:#fff;padding:20px;border:1px solid #ddd;border-radius:0 0 8px 8px">
            <p>{len(alerts)} KPI issue(s) require attention:</p>
            <table style="width:100%;border-collapse:collapse">
              <thead><tr style="background:#f5f5f5">
                <th style="padding:10px;text-align:left">Field</th>
                <th style="padding:10px;text-align:left">KPI</th>
                <th style="padding:10px;text-align:left">Status</th>
                <th style="padding:10px;text-align:left">Detail</th>
              </tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
        </body></html>"""

        text = f"NuHarvest KPI Alert — {len(alerts)} issue(s)\n\n"
        for a in alerts:
            text += f"• {a['field']} | {a['kpi']} | {a['severity']} — {a['message']}\n"

        msg = EmailMultiAlternatives(
            f"[NuHarvest] {len(alerts)} KPI Alert(s) — {timezone.now().strftime('%d %b %Y')}",
            text, settings.DEFAULT_FROM_EMAIL, recipients
        )
        msg.attach_alternative(html, "text/html")
        msg.send()
        return JsonResponse({"sent": True, "alert_count": len(alerts)})

    except Exception as e:
        return JsonResponse({"sent": False, "reason": str(e)})


# ── Load initial Excel data ───────────────────────────────────────────────────
@login_required
def load_initial_data(request):
    if request.method == "POST":
        try:
            profile = request.user.profile
            if profile.role != "admin":
                return JsonResponse({"error": "Admin only"}, status=403)
        except: pass
        dept, _ = Department.objects.get_or_create(
            code="PLANT", defaults={"name": "Planting", "colour": "#1B4332"}
        )
        created, updated = load_excel_to_db(dept)
        return JsonResponse({"created": created, "updated": updated})
    return JsonResponse({"error": "POST only"}, status=405)
