import smtplib
from email.message import EmailMessage
import csv
import time
import random
import argparse
import os
import datetime

def load_env(env_path):
    # Start with actual OS environment variables (set by Render, Docker, etc.)
    env_vars = dict(os.environ)
    # Override/extend with values from .env file if it exists (local development)
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    return env_vars

def get_email_content(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        return f.read()

def send_email(to_email, subject, body, attachment_path, env_vars):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = env_vars.get('FROM_EMAIL')
    msg['To'] = to_email
    msg.set_content(body)

    if os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            file_data = f.read()
            # Set attachment type depending on what attachment.jpg actually is
            msg.add_attachment(file_data, maintype='image', subtype='jpeg', filename=os.path.basename(attachment_path))
    else:
        print(f"Warning: Attachment {attachment_path} not found.")

    try:
        host = env_vars.get('SMTP_HOST')
        port = int(env_vars.get('SMTP_PORT', 587))
        user = env_vars.get('SMTP_USER')
        password = env_vars.get('SMTP_PASS')
        use_ssl = env_vars.get('SMTP_USE_SSL', 'false').lower() == 'true'

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True, ""
    except Exception as e:
        error_msg = str(e)
        print(f"Failed to send email to {to_email}: {error_msg}")
        return False, error_msg

def main():
    parser = argparse.ArgumentParser(description="Send emails to leads in a CSV file.")
    parser.add_argument('--test', action='store_true', help="Send test emails to predefined addresses.")
    parser.add_argument('--subject', type=str, default="Enhancing Your Digital Presence", help="Subject of the email.")
    args = parser.parse_args()

    base_dir = '/Users/kartik./Developer/automations/klyro'
    env_path = os.path.join(base_dir, '.env')
    email_txt_path = os.path.join(base_dir, 'email.txt')
    attachment_path = os.path.join(base_dir, 'attachment.jpg')
    csv_path = os.path.join(base_dir, '0.csv')
    log_file_path = os.path.join(base_dir, 'sent_emails_log.txt')

    env_vars = load_env(env_path)
    if not all(k in env_vars for k in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'FROM_EMAIL']):
        print("Missing required SMTP configurations in .env file.")
        return

    try:
        body = get_email_content(email_txt_path)
    except FileNotFoundError:
        print(f"Email body file not found: {email_txt_path}")
        return

    subject = args.subject

    if args.test:
        test_emails = ['kartikgoutam7@gmail.com', 'kartiksih07@gmail.com']
        for email in test_emails:
            print(f"Sending test email to {email}...")
            success, error_msg = send_email(email, subject, body, attachment_path, env_vars)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                if success:
                    print(f"Successfully sent test email to {email}")
                    log_file.write(f"[{timestamp}] SUCCESS: test email to {email}\n")
                else:
                    print(f"Failed to send to {email}")
                    log_file.write(f"[{timestamp}] FAILED: test email to {email} - Error: {error_msg}\n")
        return

    print("Starting production run...")
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return

    sent_emails = set()
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if 'SUCCESS:' in line:
                    email_part = line.split('SUCCESS:')[1].strip()
                    if email_part.startswith('test email to '):
                        email_part = email_part.replace('test email to ', '')
                    sent_emails.add(email_part.lower())

    success_count = 0
    fail_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get('email', '').strip()
            if email and email.lower() != 'not-applicable':
                if email.lower() in sent_emails:
                    print(f"Skipping {email}, already sent.")
                    continue
                print(f"Sending email to {email}...")
                success, error_msg = send_email(email, subject, body, attachment_path, env_vars)
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with open(log_file_path, 'a', encoding='utf-8') as log_file:
                    if success:
                        success_count += 1
                        print(f"Success. ({success_count} sent, {fail_count} failed)")
                        log_file.write(f"[{timestamp}] SUCCESS: {email}\n")
                    else:
                        fail_count += 1
                        log_file.write(f"[{timestamp}] FAILED: {email} - Error: {error_msg}\n")
                
                
                # Random delay between 2 and 5 seconds to speed up sending
                delay = random.uniform(2.0, 5.0)
                print(f"Sleeping for {delay:.2f} seconds before next email...")
                time.sleep(delay)

    print(f"Finished. Total sent: {success_count}, Total failed: {fail_count}")

if __name__ == '__main__':
    main()
