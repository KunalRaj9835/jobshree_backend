import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Thread pool for async email sending
executor = ThreadPoolExecutor(max_workers=3)

# SMTP Configuration for different providers
SMTP_CONFIGS = {
    'gmail': {'host': 'smtp.gmail.com', 'port': 587, 'use_tls': True},
    'outlook': {'host': 'smtp-mail.outlook.com', 'port': 587, 'use_tls': True},
    'yahoo': {'host': 'smtp.mail.yahoo.com', 'port': 587, 'use_tls': True},
    'office365': {'host': 'smtp.office365.com', 'port': 587, 'use_tls': True},
    'custom': {
        'host': os.getenv('SMTP_HOST', 'smtp.example.com'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'use_tls': True
    }
}

def detect_email_provider(email_address):
    """Auto-detect email provider from email address"""
    email_lower = email_address.lower()
    if '@gmail.com' in email_lower:
        return 'gmail'
    elif '@outlook.com' in email_lower or '@hotmail.com' in email_lower:
        return 'outlook'
    elif '@yahoo.com' in email_lower:
        return 'yahoo'
    else:
        return 'custom'

def get_smtp_config():
    """Get SMTP configuration based on provider"""
    provider = os.getenv('MAIL_PROVIDER', 'auto').lower()
    sender_email = os.getenv('MAIL_USERNAME', '')
    
    if provider == 'auto':
        provider = detect_email_provider(sender_email)
        print(f"📧 Auto-detected provider: {provider}")
    
    return SMTP_CONFIGS.get(provider, SMTP_CONFIGS['custom'])

def send_email_sync(to_email, subject, html_content, text_content=None):
    """Send email via SMTP"""
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    sender_name = os.getenv('MAIL_FROM_NAME', ' ')
    
    if not sender_email or not sender_password:
        print("❌ Email credentials not configured")
        print_email_to_console(to_email, subject, html_content)
        return False
    
    smtp_config = get_smtp_config()
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = to_email
    
    if text_content:
        message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))
    
    try:
        server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
        server.ehlo()
        if smtp_config['use_tls']:
            server.starttls()
            server.ehlo()
        
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        
        print(f"✅ Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print_email_to_console(to_email, subject, html_content)
        return False

def print_email_to_console(to_email, subject, html_content):
    """Fallback: Print email to console for testing"""
    import re
    print("\n" + "="*70)
    print("📧 EMAIL (Console Mode)")
    print("="*70)
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    otp_match = re.search(r'>(\d{6})<', html_content)
    if otp_match:
        print(f"🔑 OTP: {otp_match.group(1)}")
    print("="*70 + "\n")

async def send_otp_email(email, otp, name="User"):
    """Send OTP email asynchronously"""
    subject = "Password Reset OTP - o"
    
    text_content = f"""
Hello {name},

Your OTP for password reset is: {otp}

This OTP is valid for 10 minutes only.

---
JobShree
    """
    
    html_content = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
        <tr><td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <tr>
                    <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:40px;text-align:center;">
                        <h1 style="color:#fff;margin:0;font-size:28px;">🔐 Password Reset</h1>
                    </td>
                </tr>
                <tr>
                    <td style="padding:40px 30px;">
                        <p style="font-size:16px;color:#2d3748;margin:0 0 20px;">Hello <strong>{name}</strong>,</p>
                        <p style="font-size:15px;color:#4a5568;margin:0 0 30px;">You requested to reset your password. Use the OTP below:</p>
                        <table width="100%" style="margin:30px 0;"><tr><td align="center">
                            <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:12px;padding:30px;display:inline-block;">
                                <p style="color:#fff;font-size:13px;margin:0 0 15px;text-transform:uppercase;letter-spacing:2px;">Your OTP Code</p>
                                <div style="background:rgba(255,255,255,0.2);border-radius:10px;padding:20px 40px;">
                                    <span style="color:#fff;font-size:36px;font-weight:bold;letter-spacing:10px;font-family:'Courier New',monospace;">{otp}</span>
                                </div>
                            </div>
                        </td></tr></table>
                        <p style="background:#fff3cd;border-left:4px solid #ffc107;padding:15px;border-radius:6px;color:#856404;font-size:14px;">
                            <strong>⏰ Important:</strong> This OTP is valid for <strong>10 minutes</strong> only.
                        </p>
                        <p style="font-size:14px;color:#718096;margin:25px 0 0;">If you didn't request this, please ignore this email.</p>
                    </td>
                </tr>
                <tr>
                    <td style="background:#f8f9fa;padding:25px;border-top:1px solid #e2e8f0;text-align:center;">
                        <p style="margin:0;font-size:13px;color:#718096;">This is an automated message from <strong style="color:#667eea;">JobShree</strong></p>
                        <p style="margin:15px 0 0;font-size:12px;color:#a0aec0;">©️ 2026 Naukri. All rights reserved.</p>
                    </td>
                </tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
    """
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, send_email_sync, email, subject, html_content, text_content)