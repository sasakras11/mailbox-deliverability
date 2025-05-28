document.addEventListener('DOMContentLoaded', () => {
    // Scheduled Task Configuration Elements
    const storedApiKeyInput = document.getElementById('storedApiKey');
    const newScheduledCampaignIdInput = document.getElementById('newScheduledCampaignId');
    const addCampaignIdButton = document.getElementById('addCampaignIdButton');
    const scheduledCampaignsListUl = document.getElementById('scheduledCampaignsList');
    const saveConfigButton = document.getElementById('saveConfigButton');
    const configStatusP = document.getElementById('configStatus');

    // Manual Check Elements
    const manualApiKeyInput = document.getElementById('manualApiKey');
    const manualCampaignIdInput = document.getElementById('manualCampaignId');
    const runManualCheckButton = document.getElementById('runManualCheckButton');

    // Scheduling Elements
    const scheduleSelect = document.getElementById('schedule');
    const cronInfoOutputDiv = document.getElementById('cronInfoOutput');

    // Log Output
    const logOutputDiv = document.getElementById('logOutput');

    let scheduledCampaignIds = []; // In-memory list of campaign IDs for the UI

    // --- Utility Functions ---
    function escapeHtml(unsafe) {
        if (unsafe === null || typeof unsafe === 'undefined') return '';
        return unsafe.toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function displayLog(message, isError = false) {
        const p = document.createElement('p');
        p.textContent = message;
        if (isError) p.style.color = 'red';
        logOutputDiv.insertBefore(p, logOutputDiv.firstChild); // Add new logs to the top
    }
    
    function clearLogs() {
        logOutputDiv.innerHTML = '';
    }

    function displayConfigStatus(message, isError = false) {
        configStatusP.textContent = message;
        configStatusP.style.color = isError ? 'red' : 'green';
        setTimeout(() => { configStatusP.textContent = ''; }, 3000);
    }

    // --- Scheduled Task Configuration UI Logic ---
    function renderScheduledCampaignsList() {
        scheduledCampaignsListUl.innerHTML = '';
        if (scheduledCampaignIds.length === 0) {
            const li = document.createElement('li');
            li.textContent = 'No campaign IDs added yet.';
            li.style.fontStyle = 'italic';
            scheduledCampaignsListUl.appendChild(li);
            return;
        }
        scheduledCampaignIds.forEach((id, index) => {
            const li = document.createElement('li');
            li.textContent = id;
            const removeButton = document.createElement('button');
            removeButton.textContent = 'Remove';
            removeButton.classList.add('remove-btn');
            removeButton.onclick = () => {
                scheduledCampaignIds.splice(index, 1);
                renderScheduledCampaignsList();
            };
            li.appendChild(removeButton);
            scheduledCampaignsListUl.appendChild(li);
        });
    }

    addCampaignIdButton.addEventListener('click', () => {
        const newId = newScheduledCampaignIdInput.value.trim();
        if (newId && !scheduledCampaignIds.includes(newId)) {
            scheduledCampaignIds.push(newId);
            renderScheduledCampaignsList();
            newScheduledCampaignIdInput.value = '';
        } else if (scheduledCampaignIds.includes(newId)) {
            displayConfigStatus('Campaign ID already added.', true);
        }
    });

    // --- API Calls for Configuration ---
    async function loadConfiguration() {
        try {
            const response = await fetch('/api/get-config');
            const config = await response.json();
            if (response.ok) {
                storedApiKeyInput.value = config.apiKey || '';
                scheduledCampaignIds = Array.isArray(config.campaignIds) ? config.campaignIds : [];
                renderScheduledCampaignsList();
            } else {
                displayConfigStatus(`Error loading config: ${config.error || 'Unknown error'}`, true);
                scheduledCampaignIds = []; // Reset on error
                renderScheduledCampaignsList();
            }
        } catch (error) {
            displayConfigStatus(`Network error loading config: ${error.message}`, true);
            scheduledCampaignIds = []; // Reset on error
            renderScheduledCampaignsList();
        }
    }

    saveConfigButton.addEventListener('click', async () => {
        const apiKey = storedApiKeyInput.value.trim();
        if (!apiKey) {
            displayConfigStatus('API Key for scheduled tasks cannot be empty.', true);
            return;
        }
        saveConfigButton.disabled = true;
        displayConfigStatus('Saving...', false);
        try {
            const response = await fetch('/api/save-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ apiKey: apiKey, campaignIds: scheduledCampaignIds })
            });
            const result = await response.json();
            if (response.ok && result.status === 'success') {
                displayConfigStatus(result.message || 'Configuration saved successfully!', false);
            } else {
                displayConfigStatus(result.message || 'Failed to save configuration.', true);
            }
        } catch (error) {
            displayConfigStatus(`Network error saving config: ${error.message}`, true);
        }
        saveConfigButton.disabled = false;
    });

    // --- Manual Check Logic ---
    runManualCheckButton.addEventListener('click', async () => {
        const apiKey = manualApiKeyInput.value.trim();
        const campaignId = manualCampaignIdInput.value.trim();

        if (!apiKey || !campaignId) {
            clearLogs();
            displayLog('Manual Check: API Key and Campaign ID are required.', true);
            return;
        }

        clearLogs();
        displayLog('Manual Check: Processing...');
        runManualCheckButton.disabled = true;

        try {
            const response = await fetch('/api/check-and-disable-manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ apiKey, campaignId }),
            });
            const result = await response.json();
            clearLogs();
            if (result.logs && result.logs.length > 0) {
                result.logs.forEach(log => displayLog(escapeHtml(log)));
            } else if (response.ok) {
                displayLog('Manual Check: Request processed, but no specific logs returned.');
            } else {
                displayLog(`Manual Check Error: ${result.message || response.statusText}`, true);
            }
        } catch (error) {
            clearLogs();
            displayLog(`Manual Check Network Error: ${error.message}`, true);
        }
        runManualCheckButton.disabled = false;
    });

    // --- Scheduling Info Logic ---
    function updateCronInfo() {
        const selectedValue = scheduleSelect.value;
        cronInfoOutputDiv.innerHTML = 
            `<p><strong>Vercel Cron Setup:</strong></p>
             <p>To use this schedule, add/update the following in your <code>vercel.json</code> file:</p>
             <pre>{
  "crons": [
    {
      "path": "/api/trigger-check-scheduled",
      "schedule": "${selectedValue}"
    }
  ]
}</pre>
             <p>The cron job will use the API Key and Campaign IDs saved in the 'Scheduled Task Configuration' section.</p>`;
    }
    scheduleSelect.addEventListener('change', updateCronInfo);

    // --- Initial Load ---
    loadConfiguration();
    renderScheduledCampaignsList(); // Initial render for empty state
    updateCronInfo(); // Show initial cron info
    clearLogs();
    displayLog("Page loaded. Configure scheduled tasks or run a manual check.");
});
