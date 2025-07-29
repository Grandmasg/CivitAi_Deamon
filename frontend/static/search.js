// --- API Base URL Helper ---
function getApiBaseUrl() {
  // Try to read from window.ModelManager.config.active_port_back if available
  if (window.ModelManager && window.ModelManager.config && window.ModelManager.config.active_port_back) {
    return `http://localhost:${window.ModelManager.config.active_port_back}`;
  }
  // Fallback to window.API_BASE_URL if set
  if (window.API_BASE_URL) return window.API_BASE_URL;
  // Default
  return 'http://localhost:8000';
}


// Attach event handlers to all Details buttons to open the modal
function attachDetailButtonHandlers() {
  // Support both .details-btn and [data-action='details'] for backward compatibility
  document.querySelectorAll('.details-btn, .btn[data-action="details"]').forEach(btn => {
    btn.onclick = function(e) {
      e.preventDefault();
      const modelId = btn.getAttribute('data-model-id');
      if (modelId && typeof showModelDetail === 'function') {
        showModelDetail(modelId);
      }
    };
  });
}

// --- Mark Download Finished Helper ---
async function markDownloadFinished(modelId, modelVersionId = null) {
  const now = new Date().toISOString();
  let queue = getDownloadQueue();
  const beforeQueue = JSON.stringify(queue);
  queue = removeEntriesFromQueue(queue, modelId, modelVersionId);
  setDownloadQueue(queue);
  const afterQueue = JSON.stringify(queue);
  // console.log(`[QUEUE][${now}] markDownloadFinished called for modelId=${modelId}, modelVersionId=${modelVersionId}`);
  // console.log(`[QUEUE][${now}] Queue before: ${beforeQueue}`);
  // console.log(`[QUEUE][${now}] Queue after: ${afterQueue}`);
  updateDownloadModels(modelId, modelVersionId);
  updateUI();
  if (getDownloadQueue().length === 0) {
    isProcessingQueue = false;
  }
}

// Remove entries from queue based on modelId and modelVersionId
function removeEntriesFromQueue(queue, modelId, modelVersionId) {
  return queue.filter(q =>
    !(String(q.model_id) === String(modelId) &&
      (String(q.model_version_id) === String(modelVersionId) || !modelVersionId))
  );
}

// --- Update Download Models Helper ---
function updateDownloadModels(modelId, modelVersionId) {
  let newEntry = { model_id: modelId, model_version_id: modelVersionId };
  try {
    let downloadedModels = JSON.parse(localStorage.getItem('downloadedModels') || '[]');
    const alreadyDownloaded = downloadedModels.some(d => {
      if (typeof d === 'object' && d !== null) {
        return String(d.model_id) === String(newEntry.model_id) && (!newEntry.model_version_id || String(d.model_version_id) === String(newEntry.model_version_id));
      }
      return String(d) === String(newEntry.model_id);
    });
    if (!alreadyDownloaded) {
      downloadedModels.push(newEntry);
      localStorage.setItem('downloadedModels', JSON.stringify(downloadedModels));
    }
  } catch (e) {
    const now = new Date().toISOString();
    console.error(`[QUEUE][${now}] markDownloadFinished: error updating downloadedModels`, e);
  }
}

// Update UI elements that depend on download status
function updateUI() {
  updateDownloadButtons();
  updateDownloadProgressBar();
  if (typeof render === 'function') render();
}


// Restore hasMoreTags helper for Handlebars templates
Handlebars.registerHelper('hasMoreTags', function(array, limit, options) {
  if (!Array.isArray(array)) return false;
  if (typeof options.fn !== 'function') return false;
  if (array.length > limit) {
    return options.fn(this);
  } else if (typeof options.inverse === 'function') {
    return options.inverse(this);
  }
  return '';
});


// --- JWT Helper ---
async function getJwt() {
  if (
    window.ModelManager &&
    window.ModelManager.config &&
    window.ModelManager.config.jwt_secret &&
    window.jwtEncode
  ) {
    const payload = {
      sub: "user",
      role: "user",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 3600
    };
    try {
      const token = await window.jwtEncode(payload, window.ModelManager.config.jwt_secret);
      if (token && typeof token === 'string' && token.length > 0) return token;
    } catch (e) {
      console.error('[JWT] Error encoding JWT:', e);
    }
  }
  // Fallback: try to get from config or localStorage
  if (window.ModelManager && window.ModelManager.config && window.ModelManager.config.jwt) {
    return window.ModelManager.config.jwt;
  }
  if (localStorage.getItem('jwt')) {
    return localStorage.getItem('jwt');
  }
  return null;
}


// --- Download Queue Management ---
function getDownloadQueue() {
  try {
    const queue = JSON.parse(localStorage.getItem('downloadQueue') || '[]');
    // Always return as array of objects {model_id, model_version_id}
    if (Array.isArray(queue) && queue.length > 0 && typeof queue[0] !== 'object') {
      // Old format: array of ids, convert
      return queue.map(id => ({ model_id: id, model_version_id: null }));
    }
    return queue;
  } catch (e) {
    return [];
  }
}

// Set download queue in localStorage
function setDownloadQueue(queue) {
  // Always store as array of objects {model_id, model_version_id}, no deduplication
  const formatted = queue.map(item => {
    if (typeof item === 'object' && item !== null && 'model_id' in item) return item;
    return { model_id: item, model_version_id: null };
  });
  // console.log('[QUEUE][DEBUG] setDownloadQueue before:', JSON.stringify(queue));
  // console.log('[QUEUE][DEBUG] setDownloadQueue after:', JSON.stringify(formatted));
  localStorage.setItem('downloadQueue', JSON.stringify(formatted));
}

// Build manifest object for download
function buildManifest(modelId, modelVersionId = null) {
  const model = state.result.find(m => String(m.id) === String(modelId));
  if (!model) return null;
  let mv = null;
  if (Array.isArray(model.modelVersions) && model.modelVersions.length > 0) {
    if (modelVersionId) {
      mv = model.modelVersions.find(v => String(v.id) === String(modelVersionId));
    }
    if (!mv) {
      mv = model.modelVersions[0];
    }
  } else {
    mv = {};
  }
  let file = {};
  let sha256 = '';
  let filename = '';
  let url = '';
  if (Array.isArray(mv.files) && mv.files.length > 0) {
    file = mv.files[0];
    filename = file.name || mv.filename || model.filename || '';
    sha256 = (file.hashes && file.hashes.SHA256) ? file.hashes.SHA256 : '';
    url = file.downloadUrl || mv.downloadUrl || model.url || '';
  }
  return {
    model_id: model.id,
    model_version_id: mv.id,
    model_type: model.type || mv.type || '',
    baseModel: mv.baseModel || model.baseModel || '',
    sha256,
    url,
    filename
  };
}

// --- Post Manifest to Backend ---
async function postManifestToBackend(modelId, modelVersionId = null, justQueue = false) {
  const manifest = buildManifest(modelId, modelVersionId);
  if (!manifest) {
    console.warn('[QUEUE] postManifestToBackend: model not found for id', modelId, 'version', modelVersionId);
    return;
  }
  // console.log('[DEBUG][QUEUE] POST manifest:', manifest);
  let jwt = await getJwt();
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(jwt ? { 'Authorization': `Bearer ${jwt}` } : {})
      },
      body: JSON.stringify(justQueue ? { ...manifest, queue_only: true } : manifest)
    });
    // ...existing code...
  } catch (err) {
    console.error('[QUEUE] postManifestToBackend: error', err);
    showBootstrapAlert('Failed to sync with backend for download queue. Please check your connection or backend status.', 'danger');
  }
}

// Add to download queue and immediately POST manifest
function addToDownloadQueue(modelId) {
  let queue = getDownloadQueue();
  // Find modelVersionId
  let modelVersionId = null;
  const model = state.result.find(m => m.id == modelId);
  if (model && Array.isArray(model.modelVersions) && model.modelVersions.length > 0) {
    modelVersionId = model.modelVersions[0].id;
  }
  queue.push({ model_id: modelId, model_version_id: modelVersionId });
  setDownloadQueue(queue);
  postManifestToBackend(modelId, modelVersionId, false);
  // Only update the download button and progress bar for this model
  updateDownloadButtons();
  updateDownloadProgressBar();
  // Do NOT call render() here to avoid rerendering video elements
}

// Remove from download queue by modelId and modelVersionId
function removeFromDownloadQueue(modelId) {
  let queue = getDownloadQueue();
  // Remove by model_id and model_version_id
  let modelVersionId = null;
  const model = state.result.find(m => m.id == modelId);
  if (model && Array.isArray(model.modelVersions) && model.modelVersions.length > 0) {
    modelVersionId = model.modelVersions[0].id;
  }
  const idx = queue.findIndex(q => String(q.model_id) === String(modelId) && (!modelVersionId || String(q.model_version_id) === String(modelVersionId)));
  if (idx !== -1) {
    queue.splice(idx, 1);
    setDownloadQueue(queue);
    updateDownloadButtons();
    updateDownloadProgressBar();
    if (typeof render === 'function') render();
  }
}

// Get the next item in the download queue
function getNextInQueue() {
  let queue = getDownloadQueue();
  return queue.length > 0 ? queue[0] : null;
}

// Clear the download queue
function clearDownloadQueue() {
  setDownloadQueue([]);
}

// --- Download Queue Processor ---
let isProcessingQueue = false;
let hasSyncedQueue = false;
async function processDownloadQueue() {
  if (isProcessingQueue) {
    // Already processing; skip
    return;
  }
  const queueItems = getDownloadQueue();
  if (!queueItems.length) {
    isProcessingQueue = false;
    // Queue empty at start; skip
    return;
  }
  isProcessingQueue = true;
  updateDownloadButtons();
  // Immediately POST every manifest in the queue, do not wait for backend confirmation
  for (const item of queueItems) {
    console.log('[QUEUE] Processing modelId', item, '| queue before:', JSON.stringify(queueItems));
    await triggerDownloadById(item.model_id, item.model_version_id);
    updateDownloadButtons();
    updateDownloadProgressBar();
  }
  // Optionally clear the queue after posting, or let backend events handle it
  isProcessingQueue = false;
  updateDownloadButtons();
  // Do not automatically restart the processor; let user actions or backend events trigger it
  console.log('[QUEUE] processDownloadQueue: finished all');
}

// --- Download Trigger by ID ---
async function triggerDownloadById(modelId, modelVersionId = null) {
  // Find model manifest
  const manifest = buildManifest(modelId, modelVersionId);
  if (!manifest) return;
  // For debugging: log manifest instead of POSTing
  console.log('[DEBUG][QUEUE] Would POST manifest:', manifest);
  // Simulate backend confirmation and advance the queue
  // (Do NOT syncQueueWithBackend here; only sync on startup/onload)
  updateDownloadButtons();
  updateDownloadProgressBar();
  if (typeof render === 'function') render();
  if (window._downloadQueueResolve) window._downloadQueueResolve();
}

// Update download progress bar based on queue and downloaded models
function updateDownloadProgressBar() {
  // Find progress bar element (assume id 'download-progress-bar')
  const bar = document.getElementById('download-progress-bar');
  if (!bar) return;
  let queue = getDownloadQueue();
  let downloaded = [];
  let downloadStatus = window.state.downloadStatus || {};
  try {
    downloaded = JSON.parse(localStorage.getItem('downloadedModels') || '[]');
  } catch (e) {}
  const total = queue.length + downloaded.length;
  const percent = total === 0 ? 0 : Math.round((downloaded.length / total) * 100);
  bar.style.width = percent + '%';
  // Show speed/ETA if available for active download
  let speedText = '';
  let etaText = '';
  let errorText = '';
  if (queue.length > 0) {
    const active = queue[0];
    const status = downloadStatus[active.model_id] || {};
    if (status.error) {
      errorText = `<span style='color:red'><i class='bi bi-exclamation-circle'></i> Failed: ${status.error}</span>`;
      bar.classList.add('bg-danger');
      bar.classList.remove('bg-info', 'bg-success', 'bg-warning');
    } else {
      if (status.speed) speedText = `Speed: ${status.speed}`;
      if (status.eta) etaText = `ETA: ${status.eta}`;
      bar.classList.add('bg-info');
      bar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
    }
  } else if (percent === 100) {
    bar.classList.add('bg-success');
    bar.classList.remove('bg-info', 'bg-warning', 'bg-danger');
  } else {
    bar.classList.add('bg-warning');
    bar.classList.remove('bg-success', 'bg-info', 'bg-danger');
  }
  bar.innerHTML = `Hash ${percent}.0% ${speedText ? '| ' + speedText : ''} ${etaText ? '| ' + etaText : ''} ${errorText}`;
}

// Restore limitTags helper for Handlebars templates
Handlebars.registerHelper('limitTags', function(array, limit) {
  if (!Array.isArray(array)) return [];
  return array.slice(0, limit);
});

// Restore if helper for Handlebars templates
Handlebars.registerHelper('if', function(conditional, options) {
  return conditional ? options.fn(this) : options.inverse(this);
});

// Fetch models from backend API and update state
function fetchResults(append = false) {
  state.loading = true;
  state.error = null;
  const params = new URLSearchParams();
  if (state.filters.limit) params.append('limit', state.filters.limit);
  if (state.filters.searchTerm) params.append('searchTerm', state.filters.searchTerm);
  if (state.filters.type) params.append('types', state.filters.type);
  params.append('nsfw', state.filters.nsfw ? 'true' : 'false');
  if (state.filters.sort) params.append('sort', state.filters.sort);
  if (state.filters.period) {
    let period = state.filters.period === 'All Time' ? 'AllTime' : state.filters.period;
    params.append('period', period);
  }
  // Only send cursor if not the first search
  if (state.filters.cursor) params.append('cursor', state.filters.cursor);
  fetch(`/api/models?${params.toString()}`)
    .then(async res => {
      if (!res.ok) {
        const text = await res.text();
        showBootstrapAlert(`API error: ${res.status} ${text}`, 'danger');
        throw new Error(`API error: ${res.status} ${text}`);
      }
      return res.json();
    })
    .then(data => {
      // console.log('[DEBUG] API response:', data);
      const modelsArr = Array.isArray(data.items) ? data.items : [];
      // Set nextPage from backend response (prefer nextCursor for cursor-based pagination)
      state.nextPage = (data.metadata && data.metadata.nextCursor) || data.nextCursor || data.next_cursor || null;
      // console.log('[DEBUG] state.nextPage after fetch:', state.nextPage);
      if (!modelsArr.length) {
        if (!append) {
          state.result = [];
        }
        state.loading = false;
        // console.log('state.loading (no models):', state.loading);
        state.error = 'No models returned from backend.';
        render();
        return;
      }
      // Fetch downloaded IDs from daemon backend (port 8000) with correct JWT payload
      (async () => {
        let jwt = await getJwt();
        fetch(`${getApiBaseUrl()}/api/downloaded_ids`, {
          headers: {
            ...(jwt ? { 'Authorization': `Bearer ${jwt}` } : {})
          }
        })
          .then(async res2 => {
            if (res2.status === 401) {
              const text = await res2.text();
              throw new Error('Daemon backend unauthorized (401). Please check your token or backend config.');
            }
            return res2.json();
          })
          .then(downloadedData => {
            const downloadedArr = Array.isArray(downloadedData.downloaded) ? downloadedData.downloaded : [];
            // Store downloadedArr in localStorage for later use
            try {
              localStorage.setItem('downloadedModels', JSON.stringify(downloadedArr));
            } catch (e) {
              // Ignore localStorage errors
            }
            // Mark models as downloaded if their id and version match any in downloadedArr
            const models = modelsArr.map(model => {
              let isDownloaded = false;
              if (Array.isArray(model.modelVersions) && model.modelVersions.length > 0) {
                const mv = model.modelVersions[0];
                isDownloaded = downloadedArr.some(d => d.model_id == model.id && d.model_version_id == mv.id);
              }
              return { ...model, isDownloaded };
            });
            state.result = models;
            state.loading = false;
            // console.log('state.loading (models loaded):', state.loading);
            state.error = null;
            render();
          })
          .catch(err2 => {
            // If daemon fetch fails, show error if 401, else just show models without downloaded status
            let errorMsg = null;
            if (err2 && err2.message && err2.message.includes('unauthorized')) {
              errorMsg = err2.message;
            }
            const models = modelsArr.map(model => ({
              ...model,
              isDownloaded: false
            }));
            if (append) {
              state.result = (state.result || []).concat(models);
            } else {
              state.result = models;
            }
            state.loading = false;
            console.log('state.loading (downloaded fetch error):', state.loading);
            state.error = errorMsg;
            if (errorMsg) {
              console.error(errorMsg);
            } else {
              console.warn('Could not fetch downloaded IDs from daemon:', err2);
            }
            render();
          });
      })();
    })
    .catch(err => {
      state.loading = false;
      state.error = err && err.message ? err.message : 'Failed to fetch results.';
      showBootstrapAlert(state.error, 'danger');
      console.error('Fetch error:', err);
      render();
    });
}

// --- Filter Persistence ---
const DEFAULT_FILTERS = {
  type: '',
  nsfw: false,
  period: 'All Time',
  searchTerm: '',
  limit: '24',
  sort: '',
  cursor: null
};

// Load filters from localStorage or return default filters
function loadFilters() {
  try {
    return JSON.parse(localStorage.getItem('searchFilters') || 'null') || { ...DEFAULT_FILTERS };
  } catch (e) {
    return { ...DEFAULT_FILTERS };
  }
}

// Save filters to localStorage
function saveFilters(filters) {
  try {
    localStorage.setItem('searchFilters', JSON.stringify(filters));
  } catch (e) {}
}

// Initialize global state object if not already defined
window.state = window.state || {
  filters: loadFilters(),
  tags: [],
  result: [],
  loading: false,
  error: null,
  nextPage: null,
  batchMode: false,
  batchSelected: [],
  downloaded: [],
  inQueue: [],
  downloadStatus: {},
  config: {}
};

// Ensure state is available globally
const state = window.state;

// --- Render Function ---
function render() {
  const app = document.getElementById('app');
  if (!app) {
    document.body.innerHTML = '<div style="color:red;padding:2em;text-align:center;font-size:1.5em;">Error: Missing <code>app</code> container in HTML. Please add <code><div id="app"></div></code> to your template.</div>';
    return;
  }
  if (!window.renderBatchControls || !window.renderStickyBatchBtn || !window.renderNextBtnBottom || !window.renderFilters || !window.renderResults || !window.flattenModels || !window.escapeHtml) {
    app.innerHTML = '<div style="color:red;padding:2em;text-align:center;font-size:1.2em;">Error: One or more UI modules are missing.<br>Check that all <code>static/ui/*.js</code> scripts are loaded <b>before</b> <code>search.js</code> in your HTML.</div>';
    return;
  }
  if (!state || typeof state !== 'object') {
    app.innerHTML = `<div style='color:red;padding:2em;text-align:center;font-size:1.2em;'>Render error: <code>state</code> is undefined.</div>`;
    return;
  }
  try {
    // Inject spinner into next/batch controls if loading
    let spinnerInline = state.loading ? `<div class='ms-2' id='inline-spinner'><div class='spinner-border spinner-border-sm' role='status'></div></div>` : '';
    // Patch nextAndBatch to include spinner after Next button
    let nextAndBatch = window.renderBatchControls(state);
    // Try to inject spinner after Next button if possible
    if (typeof nextAndBatch === 'string') {
      nextAndBatch = nextAndBatch.replace(/(<button[^>]*id=["']nextPageBtn["'][^>]*>.*?<\/button>)/, "$1" + spinnerInline);
    }
    let stickyBatchBtn = window.renderStickyBatchBtn(state);
    let nextBtnBottom = window.renderNextBtnBottom(state);
    window._cardToResultIdx = [];
    // console.log('[DEBUG] render() state.nextPage:', state.nextPage);
    app.innerHTML = `
      <div class="container-fluid py-2 search-main-container">
        <div class="row justify-content-center">
          <div class="col-12">
            <form class="bg-white p-3 rounded shadow-sm" id="searchForm" autocomplete="off">
              <h4 class="mb-3">🔍 Search Filters</h4>
              ${window.renderFilters(state)}
              <div class="d-flex justify-content-end mt-2 gap-2">
                <button type="submit" class="btn btn-primary" id="searchBtn">Search</button>
                <button type="button" class="btn btn-outline-secondary" id="resetFiltersBtn">Reset Filters</button>
              </div>
            </form>
            ${nextAndBatch}
            <div class="model-results mt-3 search-model-results results-grid">
              ${state.result && state.result.length > 0
                ? window.renderResults(state, window.flattenModels, window.escapeHtml, window.modelManager)
                : `<div class='search-no-results'>
                    <img src='static/no-results.svg' alt='No results' class='search-no-results-img'>
                    <div class='search-no-results-text'>No models found.<br>Try different search terms or filters.</div>
                  </div>`}
            </div>
            ${nextBtnBottom}
          </div>
        </div>
      </div>
      ${stickyBatchBtn}
      <div class="modal fade" id="modelDetailModal" tabindex="-1" aria-labelledby="modelDetailModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered search-modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="modelDetailModalLabel">Model Details</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="modelDetailModalBody"></div>
          </div>
        </div>
      </div>
      ${state.loading ? '<div class="text-center my-4"><div class="spinner-border" role="status"></div> Loading...</div>' : ''}
    `;
    // Next button logic (attach handler to all #nextPageBtn, regardless of how rendered)
    document.querySelectorAll('#nextPageBtn').forEach((nextPageBtn, idx) => {
      if (state.nextPage) {
        nextPageBtn.style.display = 'inline-block';
        nextPageBtn.disabled = false;
      } else {
        nextPageBtn.style.display = 'none';
        nextPageBtn.disabled = true;
      }
      nextPageBtn.onclick = function() {
        if (state.nextPage) {
          state.filters.cursor = state.nextPage;
          saveFilters(state.filters);
          state.loading = true;
          render();
          fetchResults(true); // append mode
        }
      };
    });
    updateDownloadButtons();
    attachDetailButtonHandlers();
    // Prevent form reload and handle search
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
      searchForm.onsubmit = function(e) {
        e.preventDefault();
        state.filters.cursor = null;
        saveFilters(state.filters);
        state.loading = true;
        render();
        fetchResults();
      };
    }
    // Reset filters button
    const resetBtn = document.getElementById('resetFiltersBtn');
    if (resetBtn) {
      resetBtn.onclick = function(e) {
        e.preventDefault();
        state.filters = { ...DEFAULT_FILTERS };
        saveFilters(state.filters);
        render();
        fetchResults();
      };
    }
  } catch (err) {
    app.innerHTML = `<div style='color:red;padding:2em;text-align:center;font-size:1.2em;'>Render error: ${err && err.message ? err.message : err}</div>`;
  }
}

// --- Sync Queue with Backend ---
async function syncQueueWithBackend() {
  // Sync frontend queue with backend queue ONLY (do not include active download)
  let backendQueue = [];
  try {
    // Prepare JWT for queue fetch
    let jwt = await getJwt();
    // Fetch queue
    const res = await fetch(`${getApiBaseUrl()}/api/queue`, {
      headers: jwt ? { 'Authorization': `Bearer ${jwt}` } : {}
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.queue)) {
        backendQueue = data.queue.map(item => {
          if (Array.isArray(item) && item.length >= 3 && typeof item[2] === 'object' && item[2] !== null) {
            return {
              model_id: String(item[2].model_id || item[2].id || ''),
              model_version_id: item[2].model_version_id !== undefined ? String(item[2].model_version_id) : null
            };
          }
          if (typeof item === 'object' && item !== null) {
            return {
              model_id: String(item.model_id || item.id || ''),
              model_version_id: item.model_version_id !== undefined ? String(item.model_version_id) : null
            };
          }
          if (typeof item === 'string') {
            let match = item.match(/['"]model_id['"]\s*[:=]\s*(\d+)/);
            let model_id = match && match[1] ? match[1] : item;
            let versionMatch = item.match(/['"]model_version_id['"]\s*[:=]\s*(\d+)/);
            let model_version_id = versionMatch && versionMatch[1] ? versionMatch[1] : null;
            return { model_id: String(model_id), model_version_id: model_version_id };
          }
          return null;
        }).filter(obj => {
          return obj && typeof obj.model_id === 'string' && /^\d+$/.test(obj.model_id);
        });
      }
    } else {
      console.warn('[QUEUE SYNC] /api/queue request failed:', res.status);
      showBootstrapAlert('Failed to sync download queue with backend. Please check your connection or backend status.', 'danger');
    }
  } catch (e) {
    console.error('[QUEUE SYNC] Error fetching /api/queue:', e);
    showBootstrapAlert('Failed to sync download queue with backend. Please check your connection or backend status.', 'danger');
    // Ignore backend errors, fallback to local queue
  }
  // Final filter: only keep items with numeric model_id
  backendQueue = backendQueue.filter(obj => typeof obj.model_id === 'string' && /^\d+$/.test(obj.model_id));
  // Always set the local queue to the backend queue, even if it's empty
  setDownloadQueue(backendQueue);
  // console.log('[DEBUG][QUEUE] After syncQueueWithBackend, queue:', JSON.stringify(getDownloadQueue()));
  // Clear activeDownloads for UI state
  window._activeDownloads = [];
  if (!hasSyncedQueue) {
    hasSyncedQueue = true;
  }
  updateDownloadButtons();
  isProcessingQueue = false;
  // DO NOT call processDownloadQueue here; let user actions or queue changes trigger it
}

// --- Startup Function ---
async function startup() {

  // Always reset cursor on page load
  if (state && state.filters) {
    state.filters.cursor = null;
    saveFilters(state.filters);
  }
  if (window.ModelManager && typeof window.ModelManager.init === 'function') {
    await window.ModelManager.init();
  }
  await syncQueueWithBackend();
  fetchResults();
  // WebSocket: always send JWT if available
  if (window.ModelManager && window.ModelManager.config && window.ModelManager.config.active_port_back) {
    let jwt = await getJwt();
    let wsUrl = `ws://localhost:${window.ModelManager.config.active_port_back}/ws/downloads`;
    if (jwt) wsUrl += `?token=${encodeURIComponent(jwt)}`;
    window._ws = new WebSocket(wsUrl);
    window._ws.onopen = function() {
      // console.log('[WS] Connected to backend with JWT');
    };
    window._ws.onmessage = function(e) {
      // ...existing code for message handling...
    };
    window._ws.onerror = function(e) {
      console.error('[WS] Error:', e);
    };
    window._ws.onclose = function() {
      console.warn('[WS] Connection closed');
    };
  }
}
startup();

// Attach click handlers to detail buttons
function updateDownloadButtons() {
  // Reflect queue state and downloaded state in UI
  const queue = getDownloadQueue();
  const activeDownloads = window._activeDownloads || [];
  let downloadedModels = [];
  let downloadStatus = window.state.downloadStatus || {};
  try {
    downloadedModels = JSON.parse(localStorage.getItem('downloadedModels') || '[]');
  } catch (e) {}
  document.querySelectorAll('.download-btn').forEach((btn, idx) => {
    const modelId = btn.getAttribute('data-model-id');
    // Find the modelVersionId for this button (first version)
    let modelVersionId = null;
    let model = state.result.find(m => String(m.id) === String(modelId));
    if (model && Array.isArray(model.modelVersions) && model.modelVersions.length > 0) {
      modelVersionId = model.modelVersions[0].id;
    }
    let isDownloaded = false;
    if (downloadedModels.length > 0 && typeof downloadedModels[0] === 'object' && downloadedModels[0] !== null) {
      // Array of objects from backend: {model_id, model_version_id,...}
      isDownloaded = downloadedModels.some(d => String(d.model_id) === String(modelId) && (!modelVersionId || String(d.model_version_id) === String(modelVersionId)));
    } else {
      // Array of strings
      isDownloaded = downloadedModels.map(String).includes(modelId);
    }
    // Determine button state and style
    let btnState = {
      disabled: false,
      label: 'Download',
      class: 'btn-primary',
      title: ''
    };
    // Error indicator (no retry)
    const status = downloadStatus[modelId] || {};
    if (status.error) {
      btnState.disabled = false;
      btnState.label = 'Download';
      btnState.class = 'btn-danger';
      btnState.title = `Download failed: ${status.error}`;
      btn.innerHTML = `<i class='bi bi-exclamation-circle'></i> Download`;
      btn.onclick = null;
      return;
    }
    if (model && Array.isArray(model.modelVersions) && model.modelVersions.length > 0 && model.modelVersions[0].availability === 'EarlyAccess') {
      btnState.disabled = true;
      btnState.label = 'Early Access';
      btnState.class = 'btn-warning';
      btnState.title = 'This model is Early Access and not available for download.';
    } else if (isDownloaded) {
      btnState.disabled = true;
      btnState.label = 'Downloaded';
      btnState.class = 'btn-success';
    } else if (queue.some(q => String(q.model_id) === String(modelId) && (!modelVersionId || String(q.model_version_id) === String(modelVersionId)))) {
      btnState.disabled = true;
      btnState.label = 'In queue';
      btnState.class = 'btn-warning';
    }
    btn.disabled = btnState.disabled;
    btn.innerText = btnState.label;
    btn.classList.remove('btn-primary', 'btn-success', 'btn-warning', 'btn-secondary', 'btn-info', 'btn-danger');
    btn.classList.add(btnState.class);
    btn.title = btnState.title;
  });

  // Event delegation for download buttons
  const app = document.getElementById('app');
  if (app && !app._downloadBtnDelegated) {
    app.addEventListener('click', function(e) {
      const btn = e.target.closest('.download-btn');
      if (btn && !btn.disabled) {
        e.preventDefault();
        const modelId = btn.getAttribute('data-model-id');
        if (modelId) addToDownloadQueue(modelId);
      }
    });
    app._downloadBtnDelegated = true;
  }
}


// Update model detail modal content and show
function showModelDetail(modelId) {
  const model = state.result.find(m => m.id == modelId);
  if (!model) return;
  const modalBody = document.getElementById('modelDetailModalBody');
  if (modalBody) {
    // Description (may be in model.description or model.modelVersions[0].description)
    let description = model.description || (model.modelVersions && model.modelVersions[0] && model.modelVersions[0].description) || '';
    // List of older versions (skip the first, which is the latest)
    let olderVersions = '';
    if (Array.isArray(model.modelVersions) && model.modelVersions.length > 1) {
      olderVersions = '<ul class="list-group mb-2">';
      for (let i = 1; i < model.modelVersions.length; i++) {
        const v = model.modelVersions[i];
        olderVersions += `<li class="list-group-item">
          <strong>ID:</strong> ${v.id || 'N/A'}<br>
          <strong>Name:</strong> ${v.name || 'N/A'}<br>
          <strong>Published:</strong> ${v.publishedAt ? new Date(v.publishedAt).toLocaleString() : 'N/A'}
        </li>`;
      }
      olderVersions += '</ul>';
    }
    modalBody.innerHTML = `
      ${description ? description : '<em>No description available.</em>'}
      ${olderVersions ? `<div class="mb-2"><strong>Older Versions:</strong>${olderVersions}</div>` : ''}
      <div class="mt-3">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
      </div>
    `;
  }
  // Show the modal (Bootstrap 5)
  const modal = new bootstrap.Modal(document.getElementById('modelDetailModal'));
  modal.show();
}
