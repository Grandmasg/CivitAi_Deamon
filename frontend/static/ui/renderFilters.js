// Filters UI rendering logic for CivitAI frontend

window.renderFilters = function(state) {
  return `
    <div class="row mb-3 g-3">
      <div class="col-md-4">
        <input type="text" class="form-control" placeholder="Search by name or tag..." value="${state.filters.searchTerm}" oninput="state.filters.searchTerm=this.value; window.render()">
      </div>
      <div class="col-md-4">
        <select class="form-select" onchange="state.filters.type=this.value; window.render()">
          <option${!state.filters.type?' selected':''} value="">All types</option>
          <option${state.filters.type==='Checkpoint'?' selected':''} value="Checkpoint">Checkpoint</option>
          <option${state.filters.type==='TextualInversion'?' selected':''} value="TextualInversion">Textual Inversion</option>
          <option${state.filters.type==='Hypernetwork'?' selected':''} value="Hypernetwork">Hypernetwork</option>
          <option${state.filters.type==='AestheticGradient'?' selected':''} value="AestheticGradient">Aesthetic Gradient</option>
          <option${state.filters.type==='LORA'?' selected':''} value="LORA">LORA</option>
          <option${state.filters.type==='Controlnet'?' selected':''} value="Controlnet">Controlnet</option>
          <option${state.filters.type==='Poses'?' selected':''} value="Poses">Poses</option>
        </select>
      </div>
      <div class="col-md-4">
        <select class="form-select" onchange="state.filters.period=this.value; window.render()">
          <option${state.filters.period==='AllTime'?' selected':''}>All Time</option>
          <option${state.filters.period==='Day'?' selected':''}>Day</option>
          <option${state.filters.period==='Week'?' selected':''}>Week</option>
          <option${state.filters.period==='Month'?' selected':''}>Month</option>
          <option${state.filters.period==='Year'?' selected':''}>Year</option>
        </select>
      </div>
    </div>
    <div class="row mb-3 g-3 align-items-center">
      <div class="col-md-4">
        <select class="form-select" onchange="state.filters.limit=this.value; window.render()">
          <option${state.filters.limit==='12'?' selected':''}>12</option>
          <option${state.filters.limit==='24'?' selected':''}>24</option>
          <option${state.filters.limit==='36'?' selected':''}>36</option>
          <option${state.filters.limit==='48'?' selected':''}>48</option>
          <option${state.filters.limit==='72'?' selected':''}>72</option>
          <option${state.filters.limit==='96'?' selected':''}>96</option>
        </select>
      </div>
      <div class="col-md-4">
        <select class="form-select" onchange="state.filters.sort=this.value; window.render()">
          <option${!state.filters.sort?' selected':''} value="">Sort by</option>
          <option${state.filters.sort==='Highest Rated'?' selected':''}>Highest Rated</option>
          <option${state.filters.sort==='Most Downloaded'?' selected':''}>Most Downloaded</option>
          <option${state.filters.sort==='Newest'?' selected':''}>Newest</option>
          <option${state.filters.sort==='Most Liked'?' selected':''}>Most Liked</option>
        </select>
      </div>
      <div class="col-md-4 d-flex align-items-center gap-3">
        <label class="form-check-label me-2" for="nsfwSwitch">Show NSFW</label>
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox" id="nsfwSwitch"${state.filters.nsfw?' checked':''}
            onchange="state.filters.nsfw=this.checked; window.render()">
        </div>
      </div>
    </div>
  `;
}
