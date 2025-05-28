import os
import requests
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session

SMARTLEAD_API_BASE_URL = "https://server.smartlead.ai/api/v1"
USE_MOCK_API = True # Set to False to use actual Smartlead API

CONFIG_KEY = 'smartlead_config'

def load_app_config():
    """Load configuration from session."""
    config = session.get(CONFIG_KEY, {
        "api_key": "",
        "campaign_ids": [],
        "frequency": "180"
    })
    return config


def save_app_config(data):
    """Save configuration to session."""
    config = {
        "api_key": data.get("api_key", ""),
        "campaign_ids": data.get("campaign_ids", []),
        "frequency": data.get("frequency", "180")
    }
    session[CONFIG_KEY] = config
    return True

# --- Helper Functions (Smartlead API interactions) ---
def get_campaign_analytics(api_key, campaign_id):
    if USE_MOCK_API:
        print(f"MOCK: get_campaign_analytics called for campaign_id: {campaign_id}")
        # Simulate a scenario that would trigger mailbox disabling
        return 150, 0 # total_sent, total_replies
    url = f"{SMARTLEAD_API_BASE_URL}/campaigns/{campaign_id}/analytics?api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        # Safely access keys with .get() to avoid KeyError if a key is missing
        total_sent = data.get('sent_count', 0)
        total_replies = data.get('reply_count', 0)
        return total_sent, total_replies
    except requests.exceptions.RequestException as e:
        # Log the error or handle it as needed
        print(f"Error fetching campaign analytics for {campaign_id}: {e}")
        return 0, 0 # Return default values on error
    except json.JSONDecodeError:
        print(f"Error decoding JSON for campaign analytics {campaign_id}.")
        return 0, 0

def get_email_accounts_for_campaign(api_key, campaign_id):
    if USE_MOCK_API:
        print(f"MOCK: get_email_accounts_for_campaign called for campaign_id: {campaign_id}")
        return [
            {'id': 'mock_acc_001', 'email_address': f'leadgen1@{campaign_id}.example.com', 'mock_sent_count': 75, 'mock_reply_count': 0},
            {'id': 'mock_acc_002', 'email_address': f'outreach2@{campaign_id}.example.com', 'mock_sent_count': 75, 'mock_reply_count': 0}
        ]
    url = f"{SMARTLEAD_API_BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json() # Returns a list of email account objects
    except requests.exceptions.RequestException as e:
        print(f"Error fetching email accounts for campaign {campaign_id}: {e}")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON for email accounts {campaign_id}.")
        return []

def disable_email_account(api_key, email_account_id):
    if USE_MOCK_API:
        print(f"MOCK: disable_email_account called for email_account_id: {email_account_id}")
        return True, {'message': f'Mock: Stopped sending new emails for account {email_account_id}.'}
    url = f"{SMARTLEAD_API_BASE_URL}/email-accounts/{email_account_id}?api_key={api_key}"
    payload = {"max_email_per_day": 0}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error disabling email account {email_account_id}: {e}")
        error_message = str(e)
        # Try to get more specific error from response if available
        if response is not None and response.content:
            try:
                error_details = response.json()
                error_message = error_details.get('message', error_message)
            except json.JSONDecodeError:
                pass # Keep original error if JSON parsing fails
        return False, {"message": error_message}
    except json.JSONDecodeError:
        print(f"Error decoding JSON for disabling email account {email_account_id}.")
        return False, {"message": "JSON decode error"}

def process_campaign_check(api_key, campaign_id):
    logs = []    
    total_sent_for_campaign, total_replies_for_campaign = get_campaign_analytics(api_key, campaign_id)
    logs.append(f"Campaign {campaign_id}: Total Sent = {total_sent_for_campaign}, Total Replies = {total_replies_for_campaign}")

    # Using 1 for sent_count for easier testing. Change to 100 for production.
    if total_sent_for_campaign >= 1 and total_replies_for_campaign == 0:
        logs.append(f"Condition met for Campaign {campaign_id}: Sent >= 1 (test) and Replies == 0. Attempting to stop sending new emails from mailboxes.")
        email_accounts = get_email_accounts_for_campaign(api_key, campaign_id)
        if not email_accounts:
            logs.append(f"No email accounts found or error fetching for campaign {campaign_id}.")
        else:
            for account in email_accounts:
                account_id = account.get('id')
                account_email = account.get('email_address', 'N/A')
                mock_sent = account.get('mock_sent_count', 'N/A') # Get mock sent count
                mock_replies = account.get('mock_reply_count', 'N/A') # Get mock reply count
                if account_id:
                    success, response_data = disable_email_account(api_key, account_id)
                    if success:
                        logs.append(f"Mailbox: {account_email}, Mock Sent: {mock_sent}, Mock Replies: {mock_replies} - {response_data.get('message', 'OK').replace('disabled', 'stopped sending new emails').replace('Email account', 'account')}")
                    else:
                        logs.append(f"Failed to stop sending new emails from mailbox ID: {account_id} ({account_email}), Mock Sent: {mock_sent}, Mock Replies: {mock_replies}. Error: {response_data.get('message', 'Unknown error')}")
                else:
                    logs.append(f"Could not disable mailbox, ID missing for account: {account_email}")
    else:
        logs.append(f"Condition not met for Campaign {campaign_id}. No action taken.")
    
    return logs, total_sent_for_campaign, total_replies_for_campaign

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get-config', methods=['GET'])
def get_config_route():
    config = load_app_config()
    return jsonify(config)

@app.route('/api/save-config', methods=['POST'])
def save_config_route():
    data = request.json
    save_app_config(data)
    return jsonify({"message": "Configuration saved successfully"})

@app.route('/api/check-and-disable-manual', methods=['POST'])
def check_and_disable_manual_route():
    data = request.json
    api_key = data.get('apiKey') # API key still comes from the current input on the page
    
    config = load_app_config() # Load saved config to get campaign IDs
    campaign_ids = config.get('campaign_ids', [])

    if not api_key:
        return jsonify({'error': 'API Key is required.'}), 400
    if not campaign_ids:
        return jsonify({'error': 'No Campaign IDs configured. Please save configuration first.'}), 400

    all_logs = []
    total_sent_overall = 0
    total_replies_overall = 0
    processed_campaign_count = 0

    for campaign_id in campaign_ids:
        if not campaign_id.strip(): # Skip empty campaign IDs
            continue
        all_logs.append(f"--- Processing Campaign ID: {campaign_id} ---")
        logs, sent, replies = process_campaign_check(api_key, str(campaign_id))
        all_logs.extend(logs)
        total_sent_overall += sent
        total_replies_overall += replies
        processed_campaign_count += 1
        all_logs.append("--- End of Campaign ID: " + str(campaign_id) + " ---")

    if processed_campaign_count == 0:
        return jsonify({'logs': ['No valid campaign IDs found to process.'], 'processed_campaigns': 0}), 200

    return jsonify({'logs': all_logs, 'processed_campaigns': processed_campaign_count, 'sent_total_overall': total_sent_overall, 'replies_total_overall': total_replies_overall})

@app.route('/api/trigger-check-scheduled', methods=['GET', 'POST'])
def trigger_check_scheduled_route():
    config = load_app_config()
    api_key = config.get('api_key')
    campaign_ids = config.get('campaign_ids', []) # Expect a list of campaign IDs

    if not api_key:
        print("Scheduled Check: API key not configured.")
        return jsonify({"error": "API key not configured for scheduled checks."}), 400
    
    if not campaign_ids:
        print("Scheduled Check: No campaign IDs configured.")
        return jsonify({"message": "No campaign IDs configured for scheduled checks."}), 200

    all_logs = []
    total_sent_overall = 0
    total_replies_overall = 0
    processed_campaign_count = 0
    
    all_logs.append(f"Scheduled task started for {len(campaign_ids)} configured campaign(s).")
    print(f"Scheduled task started for {len(campaign_ids)} configured campaign(s).")

    for campaign_id in campaign_ids:
        if not str(campaign_id).strip(): # Skip empty or whitespace-only campaign IDs
            all_logs.append(f"Skipping empty campaign ID entry.")
            continue
        campaign_id_str = str(campaign_id).strip()
        all_logs.append(f"--- Processing Campaign ID: {campaign_id_str} ---")
        print(f"--- Processing Campaign ID: {campaign_id_str} ---")
        logs, sent, replies = process_campaign_check(api_key, campaign_id_str)
        all_logs.extend(logs)
        total_sent_overall += sent
        total_replies_overall += replies
        processed_campaign_count +=1
        all_logs.append(f"--- End of Campaign ID: {campaign_id_str} ---")

    summary_log = f"Scheduled task finished. Processed {processed_campaign_count} campaign(s). Total sent overall: {total_sent_overall}, Total replies overall: {total_replies_overall}."
    all_logs.append(summary_log)
    print(summary_log) # For local console logging
    
    return jsonify({'status': 'success', 'logs': all_logs, 'processed_campaigns': processed_campaign_count, 'sent_total_overall': total_sent_overall, 'replies_total_overall': total_replies_overall})

if __name__ == '__main__':
    # For local testing. 
    # The .env file will be loaded by load_dotenv() if it exists.
    # No Vercel KV specific env vars needed for this local setup.
    app.run(debug=True, port=5000)
