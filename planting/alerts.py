"""
alerts.py  –  sends HTML alert emails when KPIs breach thresholds
"""
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone


def send_alert_email(alerts: list, kpi_data: dict):
    if not alerts:
        return False

    recipients = getattr(settings, "ALERT_EMAIL_RECIPIENTS", [])
    if not recipients:
        return False

    status_emoji = {"GREEN": "✅", "ORANGE": "⚠️", "RED": "🔴"}
    subject = f"[Agri Dashboard] KPI Alert – {len(alerts)} issue(s) detected"

    # Plain-text fallback
    text_body = f"KPI Alert – {timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for a in alerts:
        text_body += f"• {a['kpi']}: {a['message']}\n"
    text_body += "\nPlease review the dashboard for details."

    # HTML body
    rows_html = ""
    for a in alerts:
        emoji = status_emoji.get(a["status"], "⚠️")
        rows_html += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee">{emoji} <strong>{a['kpi']}</strong></td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:{a['colour']};font-weight:bold">{a['status']}</td>
          <td style="padding:10px;border-bottom:1px solid #eee">{a['message']}</td>
        </tr>"""

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:640px;margin:auto">
      <div style="background:#2E7D32;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0">🌱 Agri Dashboard – KPI Alert</h2>
        <p style="color:#c8e6c9;margin:4px 0 0">{timezone.now().strftime('%A, %d %B %Y – %H:%M')}</p>
      </div>
      <div style="background:#fff;padding:20px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px">
        <p>{len(alerts)} KPI(s) require your attention:</p>
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f5f5f5">
              <th style="padding:10px;text-align:left">KPI</th>
              <th style="padding:10px;text-align:left">Status</th>
              <th style="padding:10px;text-align:left">Details</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style="margin-top:20px;font-size:13px;color:#888">
          This alert was generated automatically by the Agri Dashboard.<br>
          Log in to the dashboard to view full KPI details and historical trends.
        </p>
      </div>
    </body></html>"""

    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, recipients)
    msg.attach_alternative(html_body, "text/html")
    msg.send()
    return True
