import os
import requests
import json # For Vercel KV list storage
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from vercel_kv import KV # Import Vercel KV

load_dotenv() # Load environment variables from .env for local development

app = Flask(__name__)

# Initialize Vercel KV client
# For local development, ensure Vercel KV environment variables are set (KV_URL, etc.)
# or use a local Redis instance if vercel-kv supports it directly or via Vercel CLI dev.
kv_client = KV()

SMARTLEAD_API_BASE_URL = "https://server.smartlead.ai/api/v1"
KV_API_KEY_NAME = "SMARTLEAD_API_KEY_CONFIG"
KV_CAMPAIGN_IDS_NAME = "SMARTLEAD_CAMPAIGN_IDS_CONFIG"

# --- Helper Functions (Smartlead API interactions) ---
def get_campaign_analytics(api_key, campaign_id):
    """Fetches campaign analytics (sent, replies)."""
    url = f"{SMARTLEAD_API_BASE_URL}/campaigns/{campaign_id}/analytics?api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {
            "sent_count": int(data.get("sent_count", 0)),
            "reply_count": int(data.get("reply_count", 0)),
            "error": None
        }
    except requests.exceptions.RequestException as e:
        return {"sent_count": 0, "reply_count": 0, "error": f"API Error (Analytics for {campaign_id}): {str(e)}"}
    except ValueError:
        return {"sent_count": 0, "reply_count": 0, "error": f"API Error (Analytics for {campaign_id}): Invalid JSON response"}

def get_campaign_email_accounts(api_key, campaign_id):
    """Fetches email accounts associated with a campaign."""
    url = f"{SMARTLEAD_API_BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"API Error (Get Accounts for {campaign_id}): {str(e)}"
    except ValueError:
        return None, f"API Error (Get Accounts for {campaign_id}): Invalid JSON response"

def disable_email_account(api_key, email_account_id, campaign_id_context):
    """Sets max_email_per_day to 0 for an email account."""
    url = f"{SMARTLEAD_API_BASE_URL}/email-accounts/{email_account_id}?api_key={api_key}"
    payload = {"max_email_per_day": 0}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("ok", False), None
    except requests.exceptions.RequestException as e:
        return False, f"API Error (Disable Account {email_account_id} for campaign {campaign_id_context}): {str(e)}"
    except ValueError:
        return False, f"API Error (Disable Account {email_account_id} for campaign {campaign_id_context}): Invalid JSON response"

def process_campaign_check(api_key, campaign_id):
    logs = []
    analytics = get_campaign_analytics(api_key, campaign_id)
    if analytics["error"]:
        logs.append(f"Campaign {campaign_id}: Error fetching analytics: {analytics['error']}")
        return logs, 0, 0 # Return early if analytics fails for this campaign

    sent_count = analytics["sent_count"]
    reply_count = analytics["reply_count"]
    logs.append(f"Campaign {campaign_id} - Total Sent: {sent_count}, Total Replies: {reply_count}")

    # Condition: >= 100 emails sent AND <= 1 reply
    # IMPORTANT: Change to sent_count >= 100 for production.
    if sent_count >= 1 and reply_count <= 1: # Using 1 for easier testing.
        logs.append(f"Campaign {campaign_id}: Condition met (Sent >= 1, Replies <= 1). Attempting to disable mailboxes.")
        email_accounts, error = get_campaign_email_accounts(api_key, campaign_id)
        if error:
            logs.append(f"Campaign {campaign_id}: Error fetching email accounts: {error}")
        elif email_accounts:
            if not isinstance(email_accounts, list):
                logs.append(f"Campaign {campaign_id}: Expected a list of email accounts, got {type(email_accounts)}")
            else:
                for account in email_accounts:
                    acc_id = account.get("id")
                    acc_email = account.get("from_email", f"Unknown Email (ID: {acc_id})")
                    if acc_id:
                        success, disable_error = disable_email_account(api_key, acc_id, campaign_id)
                        if success:
                            logs.append(f"Campaign {campaign_id}: Successfully disabled mailbox: {acc_email} (ID: {acc_id})")
                        else:
                            logs.append(f"Campaign {campaign_id}: Failed to disable mailbox {acc_email} (ID: {acc_id}): {disable_error}")
                    else:
                        logs.append(f"Campaign {campaign_id}: Could not find ID for an email account: {account.get('from_email', 'Unknown')}")
        else:
            logs.append(f"Campaign {campaign_id}: No email accounts found or an error occurred while fetching them.")
    else:
        logs.append(f"Campaign {campaign_id}: Condition not met for disabling mailboxes (Sent: {sent_count}, Replies: {reply_count}).")
    
    return logs, sent_count, reply_count

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save-config', methods=['POST'])
def save_config_route():
    data = request.json
    api_key = data.get('apiKey')
    campaign_ids = data.get('campaignIds') # Expected to be a list of strings

    if not api_key or campaign_ids is None: # campaign_ids can be an empty list
        return jsonify({'status': 'error', 'message': 'API Key and Campaign IDs list are required.'}), 400
    if not isinstance(campaign_ids, list):
        return jsonify({'status': 'error', 'message': 'Campaign IDs must be a list.'}), 400

    try:
        kv_client.set(KV_API_KEY_NAME, api_key)
        kv_client.set(KV_CAMPAIGN_IDS_NAME, json.dumps(campaign_ids)) # Store list as JSON string
        return jsonify({'status': 'success', 'message': 'Configuration saved.'})
    except Exception as e:
        app.logger.error(f"Error saving to Vercel KV: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to save configuration: {str(e)}'}), 500

@app.route('/api/get-config', methods=['GET'])
def get_config_route():
    try:
        api_key = kv_client.get(KV_API_KEY_NAME)
        campaign_ids_json = kv_client.get(KV_CAMPAIGN_IDS_NAME)
        
        campaign_ids = []
        if campaign_ids_json:
            campaign_ids = json.loads(campaign_ids_json) # Parse JSON string to list
            if not isinstance(campaign_ids, list):
                # Handle case where stored data is not a list (e.g. old format or corruption)
                app.logger.warning(f"Corrupted campaign_ids in KV: {campaign_ids_json}, resetting to empty list.")
                campaign_ids = []
                kv_client.set(KV_CAMPAIGN_IDS_NAME, json.dumps([])) # Fix it in KV

        return jsonify({
            'apiKey': api_key,
            'campaignIds': campaign_ids
        })
    except Exception as e:
        app.logger.error(f"Error reading from Vercel KV: {e}")
        # Return empty/default config on error to allow UI to function
        return jsonify({'apiKey': '', 'campaignIds': [], 'error': f'Failed to load configuration: {str(e)}'}), 500

@app.route('/api/check-and-disable-manual', methods=['POST'])
def check_and_disable_manual_route(): # Renamed to avoid confusion
    data = request.json
    api_key = data.get('apiKey')
    campaign_id = data.get('campaignId')

    if not api_key or not campaign_id:
        return jsonify({'logs': ['API Key and Campaign ID are required for manual check.'], 'sent': 0, 'replies': 0}), 400

    logs, sent, replies = process_campaign_check(api_key, str(campaign_id)) # Ensure campaign_id is string
    return jsonify({'logs': logs, 'sent_total_for_campaign': sent, 'replies_total_for_campaign': replies})

@app.route('/api/trigger-check-scheduled', methods=['POST']) # For Vercel Cron
def trigger_check_scheduled_route():
    # Security: In a real Vercel environment, you might add a secret header check if desired.
    # This endpoint is intended to be called by Vercel's internal cron system.
    all_logs = []
    total_sent_across_campaigns = 0
    total_replies_across_campaigns = 0
    processed_campaign_count = 0

    try:
        api_key = kv_client.get(KV_API_KEY_NAME)
        campaign_ids_json = kv_client.get(KV_CAMPAIGN_IDS_NAME)

        if not api_key:
            log_message = "Scheduled task: SMARTLEAD_API_KEY not found in Vercel KV configuration."
            print(log_message)
            all_logs.append(log_message)
            return jsonify({'status': 'error', 'message': log_message, 'logs': all_logs}), 400
        
        campaign_ids = []
        if campaign_ids_json:
            campaign_ids = json.loads(campaign_ids_json)
        
        if not campaign_ids:
            log_message = "Scheduled task: No campaign IDs found in Vercel KV configuration."
            print(log_message)
            all_logs.append(log_message)
            return jsonify({'status': 'info', 'message': log_message, 'logs': all_logs})

        all_logs.append(f"Scheduled task started for {len(campaign_ids)} campaign(s).")
        for campaign_id in campaign_ids:
            campaign_id_str = str(campaign_id) # Ensure it's a string
            logs, sent, replies = process_campaign_check(api_key, campaign_id_str)
            all_logs.extend(logs)
            total_sent_across_campaigns += sent
            total_replies_across_campaigns += replies
            processed_campaign_count +=1
            all_logs.append("---") # Separator between campaign logs

        summary_log = f"Scheduled task finished. Processed {processed_campaign_count} campaign(s). Total sent across checked campaigns: {total_sent_across_campaigns}, Total replies: {total_replies_across_campaigns}."
        all_logs.append(summary_log)
        print(summary_log)
        # Print all individual logs for Vercel function logs
        for log_entry in all_logs:
            print(log_entry)
        
        return jsonify({'status': 'success', 'logs': all_logs, 'processed_campaigns': processed_campaign_count})

    except Exception as e:
        error_log = f"Scheduled task error: {str(e)}"
        app.logger.error(error_log)
        print(error_log)
        all_logs.append(error_log)
        return jsonify({'status': 'error', 'message': error_log, 'logs': all_logs}), 500

if __name__ == '__main__':
    # For local testing, ensure Vercel KV env vars are set or use a local Redis.
    # Example: export KV_URL="redis://localhost:6379"
    app.run(debug=True)

