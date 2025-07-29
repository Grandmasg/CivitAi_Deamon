// ws-ui.js: WebSocket UI integration for CivitAI Daemon
// Listens to backend events and updates Bootstrap alerts and progress bars

(function() {
  // DEBUG: Log all incoming WebSocket events
  function debugLogWsEvent(event, data) {
    if (event !== "queue_empty") { /*console.log('[WS-UI] Event:', event, data);*/ }
    if (data && data.model_id) {
      const card = document.querySelector(`.model-card[data-model-id="${data.model_id}"]`);
      if (card) {
        // console.log(`[WS-UI] Found card for model_id=${data.model_id}`);
      } else {
        // console.warn(`[WS-UI] No card found for model_id=${data.model_id}`);
      }
    }
  }
  // Helper: Show Bootstrap alert (top right, above page)
  let alertContainer = document.getElementById('civitai-alert-container');
  if (!alertContainer) {
    alertContainer = document.createElement('div');
    alertContainer.id = 'civitai-alert-container';
    alertContainer.style.position = 'fixed';
    alertContainer.style.top = '20px';
    alertContainer.style.right = '20px';
    alertContainer.style.zIndex = '2000';
    alertContainer.style.width = '450px';
    document.body.appendChild(alertContainer);
  }
  function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.style.marginBottom = '0.5em';
    alertDiv.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    alertContainer.prepend(alertDiv);
    setTimeout(() => alertDiv.remove(), 6000);
  }

  // Helper: Show or update progress bar
  function showProgressBar(modelId, filename, progress, kind) {
    const card = document.querySelector(`.model-card[data-model-id="${modelId}"]`);
    if (!card) return;
    const placeholder = card.querySelector('.civitai-progress-bar-placeholder');
    if (!placeholder) return;
    let bar = placeholder.querySelector('.civitai-progress-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'civitai-progress-bar progress my-2';
      bar.innerHTML = `<div class="progress-bar" role="progressbar" style="width:0%">0%</div>`;
      placeholder.appendChild(bar);
    }
    const pb = bar.querySelector('.progress-bar');
    // Always update the bar in place, never reset or create a new one for hash/download
    let progressNum = Number(progress);
    let progressStr = progressNum.toFixed(1);
    pb.style.width = progressStr + '%';
    if (kind === 'hash') {
      pb.classList.add('bg-success');
      pb.innerText = `Hash ${progressStr}%`;
    } else {
      pb.classList.remove('bg-success');
      pb.innerText = `${progressStr}%`;
    }
    // Remove any duplicate bars if present (defensive)
    const bars = placeholder.querySelectorAll('.civitai-progress-bar');
    if (bars.length > 1) {
      for (let i = 1; i < bars.length; i++) bars[i].remove();
    }
  }

  // Main event handler
  function handleWsEvent(event, data) {
    debugLogWsEvent(event, data);
    // Prevent 'queue_empty' spam: only show if >2s since last
    if (!window._lastQueueEmptyAlert) window._lastQueueEmptyAlert = 0;
    switch (event) {
      case 'in_queue':
        showAlert('info', `Queued: ${data.filename}`);
        break;
      case 'download_start':
        showAlert('primary', `Download started: ${data.filename}`);
        showProgressBar(data.model_id, data.filename, 0, 'download');
        break;
      case 'download_start':
        showAlert('primary', `Download started: ${data.filename}`);
        showProgressBar(data.model_id, data.filename, 0, 'download');
        break;
      case 'download_progress':
        showProgressBar(data.model_id, data.filename, data.progress, 'download');
        break;
      case 'download_finished':
        showAlert('success', `Download finished: ${data.filename}`);
        showProgressBar(data.model_id, data.filename, 100, 'download');
        break;
      case 'hash_start':
        showAlert('info', `Hash check started: ${data.filename}`);
        // Reset the progress bar visually to 0.0% and green for hash
        showProgressBar(data.model_id, data.filename, 0, 'hash');
        break;
      case 'hash_progress':
        showProgressBar(data.model_id, data.filename, data.progress, 'hash');
        break;
      case 'hash_finished':
        showAlert('success', `Hash verified: ${data.filename}`);
        showProgressBar(data.model_id, data.filename, 100, 'hash');
        // Update queue/downloadedModels after hash verification
        if (typeof markDownloadFinished === 'function' && data.model_id) {
          markDownloadFinished(data.model_id, data.model_version_id || null);
        }
        // Hide/remove the progress bar after a short delay
        setTimeout(() => {
          const card = document.querySelector(`.model-card[data-model-id="${data.model_id}"]`);
          if (card) {
            const placeholder = card.querySelector('.civitai-progress-bar-placeholder');
            if (placeholder) placeholder.innerHTML = '';
          }
        }, 800);
        break;
      case 'download_error':
        showAlert('danger', `Error: ${data.filename} - ${data.error}`);
        // Reset download button to normal (no retry)
        if (data.model_id) {
          const card = document.querySelector(`.model-card[data-model-id="${data.model_id}"]`);
          if (card) {
            const btn = card.querySelector('.download-btn');
            if (btn) {
              btn.disabled = false;
              btn.innerText = 'Download';
              btn.classList.remove('btn-danger', 'btn-success', 'btn-warning');
              btn.classList.add('btn-primary');
              btn.title = '';
              btn.onclick = null;
            }
          }
        }
        break;
      case 'download_skipped':
        showAlert('warning', `Skipped: ${data.filename} (${data.reason})`);
        break;
      case 'daemon_paused':
        showAlert('warning', 'Daemon paused.');
        break;
      case 'daemon_resumed':
        showAlert('info', 'Daemon resumed.');
        break;
      // Add more event handlers as needed
    }
  }

  // WebSocket connection
  function connectWs() {
    // You may want to dynamically get the JWT token
    let jwt = window.ModelManager && window.ModelManager.config && window.ModelManager.config.jwt_secret && window.jwtEncode
      ? null : null;
    // If you have a way to get a JWT, use it here
    let wsUrl = 'ws://localhost:8000/ws/downloads';
    // If you have a token, append ?token=... to wsUrl
    if (window.ModelManager && window.ModelManager.config && window.ModelManager.config.jwt_secret && window.jwtEncode) {
      const payload = {
        sub: "user",
        role: "user",
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600
      };
      window.jwtEncode(payload, window.ModelManager.config.jwt_secret).then(token => {
        wsUrl += `?token=${encodeURIComponent(token)}`;
        startWs(wsUrl);
      });
    } else {
      startWs(wsUrl);
    }
  }

  function startWs(wsUrl) {
    const ws = new window.WebSocket(wsUrl);
    ws.onmessage = function(event) {
      try {
        const msg = JSON.parse(event.data);
        handleWsEvent(msg.event, msg.data);
      } catch (e) {
        // Ignore non-JSON or unknown events
      }
    };
    ws.onclose = function() {
      setTimeout(connectWs, 2000); // Auto-reconnect
    };
  }

  // Expose for manual reconnect/debug
  window.connectCivitaiWs = connectWs;

  // Wait for ModelManager to be available before connecting WebSocket
  function waitForModelManagerAndConnect() {
    if (window.ModelManager && window.ModelManager.config) {
      connectWs();
    } else {
      setTimeout(waitForModelManagerAndConnect, 100);
    }
  }
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    waitForModelManagerAndConnect();
  } else {
    document.addEventListener('DOMContentLoaded', waitForModelManagerAndConnect);
  }
})();
