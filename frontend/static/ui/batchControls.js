// Batch controls UI logic for CivitAI frontend
// Handles batch mode toggle and next page button rendering

window.renderBatchControls = function(state) {
  return `<div class="d-flex justify-content-end align-items-center gap-2 my-4">
    <div class="form-check form-switch mb-0">
      <input class="form-check-input" type="checkbox" id="batchModeSwitch"${state.batchMode ? ' checked' : ''}>
      <label class="form-check-label ms-1" for="batchModeSwitch" title="Batch Download" style="user-select:none;cursor:pointer;">Batch</label>
    </div>
    ${state.nextPage ? `<button class="btn btn-outline-primary ms-2" id="nextPageBtn">Next</button>` : ''}
  </div>`;
}

window.renderStickyBatchBtn = function(state) {
  if (state.batchMode && state.batchSelected.length > 0) {
    return `<div id="stickyBatchDownload"><button class="btn btn-primary btn-lg shadow" id="batchDownloadBtn">⬇️ (${state.batchSelected.length})</button></div>`;
  }
  return '';
}

window.renderNextBtnBottom = function(state) {
  return state.nextPage ? `<div class="text-end my-4"><button class="btn btn-outline-primary" id="nextPageBtn">Next</button></div>` : '';
}
