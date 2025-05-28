# Smartlead Campaign Monitor & Mailbox Disabler

This Python Flask application allows you to monitor a Smartlead campaign's performance (emails sent vs. replies received) and automatically disable mailboxes associated with that campaign if certain conditions are met (e.g., >= 100 emails sent with <= 1 reply).

## Features

-   Manual check and disable via a simple web UI.
-   Input for Smartlead API Key and Campaign ID.
-   Displays logs of actions taken, including total sent, total replies, and mailboxes disabled.
-   Configurable for scheduled checks using Vercel Cron Jobs.

## Prerequisites

-   Python 3.7+
-   A Smartlead account with API access.
-   Vercel account (for deployment and cron jobs).

## API Endpoints Used (Smartlead)

-   `GET /api/v1/campaigns/{campaign_id}/analytics`: To get total sent and reply counts for a campaign.
-   `GET /api/v1/campaigns/{campaign_id}/email-accounts`: To list email accounts associated with a campaign.
-   `POST /api/v1/email-accounts/{email_account_id}`: To update `max_email_per_day` to 0 for an email account.

## Local Development Setup

1.  **Clone the repository (or create the files as listed).**

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables for scheduled tasks (optional for local manual runs):**
    Create a `.env` file in the project root:
    ```
    SMARTLEAD_API_KEY=your_smartlead_api_key_here
    SMARTLEAD_CAMPAIGN_ID=your_target_campaign_id_here
    ```
    This is used by the `/api/trigger-check-scheduled` endpoint if you test it locally or if future local scheduling is implemented.

5.  **Run the Flask application:**
    ```bash
    flask run
    # or
    python app.py
    ```
    The application will typically be available at `http://127.0.0.1:5000`.

## Using the Application (Manual Mode)

1.  Open the web interface in your browser.
2.  Enter your Smartlead API Key and the Campaign ID you want to monitor.
3.  Click "Run Check & Potentially Disable Mailboxes".
4.  Check the log output for results.

## Deployment to Vercel & Scheduled Checks

1.  **Push your code to a Git repository** (GitHub, GitLab, Bitbucket).

2.  **Import and deploy your project on Vercel.**
    -   Connect your Git repository to Vercel.
    -   Vercel should automatically detect it as a Python application using `app.py` and `requirements.txt`.

3.  **Configure Environment Variables in Vercel:**
    In your Vercel project settings, add the following environment variables:
    -   `SMARTLEAD_API_KEY`: Your Smartlead API key.
    -   `SMARTLEAD_CAMPAIGN_ID`: The specific campaign ID you want the scheduled job to monitor.

4.  **Configure Cron Jobs in `vercel.json`:**
    -   Open the `vercel.json` file in your project.
    -   Uncomment or add a cron job definition. The UI provides suggestions for the cron schedule string.
    -   Example for running every hour:
        ```json
        {
          "crons": [
            {
              "path": "/api/trigger-check-scheduled",
              "schedule": "0 * * * *"
            }
          ]
        }
        ```
    -   Commit and push this change to your Git repository. Vercel will automatically update the deployment and schedule the cron job.
    -   The cron job will hit the `/api/trigger-check-scheduled` endpoint, which uses the environment variables you set in Vercel.

## Important Notes

-   **Condition for Disabling Mailboxes:** In `app.py`, the condition is currently set to `sent_count >= 1 and reply_count <= 1` for easier testing. **For production, change this to `sent_count >= 100`** (or your desired threshold) in the `process_campaign_check` function.
-   **API Rate Limits:** Be mindful of Smartlead's API rate limits, especially if you set a very frequent cron schedule.
-   **Error Handling:** The application includes basic error handling for API requests. Check the logs in the UI (for manual runs) or Vercel deployment logs (for scheduled runs) if you encounter issues.
-   **Security for Scheduled Endpoint:** The `/api/trigger-check-scheduled` endpoint is open. For enhanced security in a production environment, you might consider adding a secret key check (e.g., a secret passed in headers and verified by the Flask app) if the endpoint were to perform more sensitive operations or if you wanted to prevent unauthorized triggering. For this specific use case with Vercel Cron, it's generally acceptable as the trigger is internal to Vercel's infrastructure based on your `vercel.json`.
