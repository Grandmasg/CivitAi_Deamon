// Utility to flatten models array for CivitAI frontend

window.flattenModels = function(arr) {
  if (!Array.isArray(arr)) return [];
  // Only return one object per model, using the first modelVersion, but preserve parent model name as modelName
  return arr.map(m => {
    if (m && Array.isArray(m.modelVersions) && m.modelVersions.length > 0) {
      return { ...m.modelVersions[0], ...m, modelName: m.name, modelid: m.id };
    }
    return m;
  });
}
