document.addEventListener('DOMContentLoaded', () => {
    // Configuration Elements
    const apiKeyInput = document.getElementById('apiKey');
    // campaignIdInput is removed, replaced by dynamic inputs
    const campaignIdsContainer = document.getElementById('campaignIdsContainer');
    const addCampaignIdButton = document.getElementById('addCampaignIdButton');
    const frequencyInput = document.getElementById('frequency');
    const saveConfigButton = document.getElementById('saveConfigButton');
    const configStatusP = document.getElementById('configStatus');

    // Diagnostics Elements
    const runDiagnosticsButton = document.getElementById('runDiagnosticsButton');
    
    // Log Output
    const logOutputPre = document.getElementById('logOutput');
    const nextRunTimerDisplay = document.getElementById('nextRunTimerDisplay'); // Added for timer

    // --- Timer Globals ---
    let nextRunIntervalId = null;
    let nextRunTargetTime = null; // Stores the absolute Date object for the next run
    let currentScheduledFrequencyMinutes = 0; // Stores the frequency for rescheduling

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
        const currentLog = logOutputPre.textContent;
        // Prepend new log entries
        const newLogEntry = escapeHtml(message) + '\n';
        if (logOutputPre.textContent === 'No activity yet.') {
            logOutputPre.textContent = newLogEntry;
        } else {
            logOutputPre.textContent = newLogEntry + logOutputPre.textContent;
        }
        // Simple error indication, could be enhanced with CSS classes
        if (isError) {
            // logOutputPre.style.color = 'red'; // Example, but might make whole log red
        }
    }
    
    function clearLogs() {
        logOutputPre.textContent = 'No activity yet.';
    }

    function displayConfigStatus(message, isError = false) {
        configStatusP.textContent = message;
        configStatusP.style.color = isError ? 'red' : 'green';
        setTimeout(() => { configStatusP.textContent = ''; }, 3000);
    }

    // --- Campaign ID Input Management ---
    function createCampaignIdInputElement(value = '') {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'campaign-id-entry';
        entryDiv.style.display = 'flex';
        entryDiv.style.alignItems = 'center';
        entryDiv.style.marginBottom = '5px';

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'campaignIdInput'; // Class for easy selection
        input.name = 'campaignId[]'; // Optional: for traditional form submission
        input.placeholder = 'Campaign ID';
        input.value = value;
        input.style.flexGrow = '1';
        input.style.marginRight = '5px';

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.innerHTML = '&times;'; // 'x' symbol
        removeButton.className = 'removeCampaignIdButton';
        removeButton.style.padding = '5px 8px';
        removeButton.addEventListener('click', () => {
            entryDiv.remove();
        });

        entryDiv.appendChild(input);
        entryDiv.appendChild(removeButton);
        return entryDiv;
    }

    addCampaignIdButton.addEventListener('click', () => {
        campaignIdsContainer.appendChild(createCampaignIdInputElement());
    });

    // --- Countdown Timer Functions ---
    function formatTimeDifference(totalSeconds) {
        if (totalSeconds < 0) totalSeconds = 0;

        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = totalSeconds % 60;

        let parts = [];
        if (h > 0) {
            parts.push(`${h} hour${h === 1 ? '' : 's'}`);
            parts.push(`${m} M`); // Show minutes (even 0) if hours are present
        } else if (m > 0) { // No hours, but minutes are present
            parts.push(`${m} M`);
        }
        // Always add seconds if other parts are present, or if it's the only unit
        if (parts.length > 0 || (h === 0 && m === 0)) {
             parts.push(`${s} sec${s === 1 ? '' : 's'}`);
        } else if (s > 0) { 
            parts.push(`${s} sec${s === 1 ? '' : 's'}`);
        }

        if (parts.length === 0 && totalSeconds === 0) return `0 secs`;
        return parts.join(' ');
    }

    function startOrUpdateNextRunTimer(frequencyInMinutes) {
        if (nextRunIntervalId) {
            clearInterval(nextRunIntervalId);
            nextRunIntervalId = null;
        }

        currentScheduledFrequencyMinutes = parseInt(frequencyInMinutes, 10);

        if (isNaN(currentScheduledFrequencyMinutes) || currentScheduledFrequencyMinutes <= 0) {
            nextRunTimerDisplay.textContent = "Next auto-run: (Not scheduled)";
            nextRunTargetTime = null;
            return;
        }
        
        // Set target time based on current time plus frequency
        // This means saving config or loading page resets the countdown from 'now'
        nextRunTargetTime = new Date(new Date().getTime() + currentScheduledFrequencyMinutes * 60 * 1000);
        nextRunTimerDisplay.textContent = "Next auto-run: (Calculating...)";

        nextRunIntervalId = setInterval(() => {
            const now = new Date();
            let remainingSeconds = Math.round((nextRunTargetTime - now) / 1000);

            if (remainingSeconds < 0) remainingSeconds = 0;

            nextRunTimerDisplay.textContent = `Next auto-run: (${formatTimeDifference(remainingSeconds)})`;

            if (remainingSeconds <= 0) {
                // Auto-run would have occurred. Reset timer for the next interval.
                // Base the next target time on the *previous* target time to maintain schedule integrity.
                if (nextRunTargetTime && currentScheduledFrequencyMinutes > 0) {
                    nextRunTargetTime = new Date(nextRunTargetTime.getTime() + currentScheduledFrequencyMinutes * 60 * 1000);
                    // The display will update on the next interval tick to show the new full duration.
                } else {
                    // Fallback if something went wrong, stop the timer.
                    clearInterval(nextRunIntervalId);
                    nextRunIntervalId = null;
                    nextRunTimerDisplay.textContent = "Next auto-run: (Error, please re-save config)";
                    return;
                }
            }
        }, 1000);
    }

    // --- Configuration API Calls ---
    async function loadConfiguration() {
        let initialFrequencyForTimer = 180; // Default to 3 hours (180 minutes)
        try {
            const response = await fetch('/api/get-config');
            const config = await response.json();
            if (response.ok) {
                apiKeyInput.value = config.api_key || '';
                
                // Handle multiple campaign IDs
                campaignIdsContainer.innerHTML = ''; // Clear existing inputs
                if (config.campaign_ids && Array.isArray(config.campaign_ids) && config.campaign_ids.length > 0) {
                    config.campaign_ids.forEach(id => {
                        campaignIdsContainer.appendChild(createCampaignIdInputElement(id));
                    });
                } else {
                    campaignIdsContainer.appendChild(createCampaignIdInputElement()); // Add one blank if none saved
                }

                const savedFrequency = parseInt(config.frequency, 10);
                if (!isNaN(savedFrequency) && savedFrequency > 0) {
                    frequencyInput.value = savedFrequency; // Set dropdown to saved value
                    initialFrequencyForTimer = savedFrequency;
                } else {
                    frequencyInput.value = initialFrequencyForTimer; // Set dropdown to default (180)
                }
            } else {
                displayConfigStatus(`Error loading config: ${config.error || 'Unknown error'}`, true);
                frequencyInput.value = initialFrequencyForTimer; // Set dropdown to default on error
            }
        } catch (error) {
            displayConfigStatus(`Network error loading config: ${error.message}`, true);
            frequencyInput.value = initialFrequencyForTimer; // Set dropdown to default on error
        }
        // Always start the timer after attempting to load config and setting frequencyInput
        startOrUpdateNextRunTimer(initialFrequencyForTimer);
    }

    saveConfigButton.addEventListener('click', async () => {
        const apiKey = apiKeyInput.value.trim();
        const frequency = frequencyInput.value.trim();

        // Collect all campaign IDs
        const campaignIdInputs = campaignIdsContainer.querySelectorAll('.campaignIdInput');
        const campaignIds = Array.from(campaignIdInputs)
                                .map(input => input.value.trim())
                                .filter(id => id !== ''); // Filter out empty strings

        if (!apiKey) {
            displayConfigStatus('Smartlead API Key cannot be empty.', true);
            return;
        }

        saveConfigButton.disabled = true;
        displayConfigStatus('Saving...', false);
        try {
            const response = await fetch('/api/save-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    api_key: apiKey, 
                    campaignIds: campaignIds, 
                    frequency: frequency 
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    displayConfigStatus(`Error saving config: ${errorJson.message || errorJson.error || 'Unknown error'}`, true);
                } catch {
                    displayConfigStatus(`Error saving config: ${errorText}`, true);
                }
                return;
            }

            const result = await response.json();
            displayConfigStatus(result.message || 'Configuration saved successfully!', false);
            const newFrequency = parseInt(frequencyInput.value, 10);
            startOrUpdateNextRunTimer(newFrequency);
        } catch (error) {
            displayConfigStatus(`Network error saving config: ${error.message}`, true);
        }
        saveConfigButton.disabled = false;
    });

    // --- Run Diagnostics Logic ---
    runDiagnosticsButton.addEventListener('click', async () => {
        const apiKey = apiKeyInput.value.trim();
        
        if (!apiKey) {
            clearLogs();
            displayLog('Diagnostics: API Key is required to run diagnostics.', true);
            return;
        }

        clearLogs();
        displayLog('Running Diagnostics for configured Campaign IDs...'); 
        runDiagnosticsButton.disabled = true;

        try {
            const response = await fetch('/api/check-and-disable-manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ apiKey }), 
            });
            const result = await response.json();
            
            // Clear the 'Running...' message before showing results
            // This assumes logs from backend are comprehensive and should replace it.
            clearLogs(); 

            if (result.logs && Array.isArray(result.logs) && result.logs.length > 0) {
                result.logs.forEach(log => displayLog(log)); // Logs are already escaped by backend or this func
            } else if (response.ok) {
                displayLog('Diagnostics: Request processed. No specific logs returned from backend. Check server console.');
            } else {
                displayLog(`Diagnostics Error: ${result.message || result.error || response.statusText}`, true);
            }
        } catch (error) {
            clearLogs();
            displayLog(`Diagnostics Network Error: ${error.message}`, true);
        } finally {
            runDiagnosticsButton.disabled = false;
        }
    });

    // --- Initial Load ---
    loadConfiguration();
    clearLogs();
    displayLog("Page loaded. Enter configuration and click 'Save Configuration', or 'Run Diagnostics Now' with current values.");
});
