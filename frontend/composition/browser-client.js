/* Same interface as the composition page's original worker transport. */
(() => {
  async function request(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    return data;
  }
  window.AntComposition = {
    prepare: async () => window.AntBrowserEngine?.prepare() ?? true,
    generate: async (strategy, brief, onProgress, options = {}) => {
      if (strategy !== "clustered") throw Error("مسار التكوين غير متاح");
      const {streamRequest} = await import("./stream.mjs");
      const params = new URLSearchParams({
        first_floor: Boolean(options.firstFloor), max_results: 2, ...options.upperProgram
      });
      if (options.fitAction) params.set("fit_action", options.fitAction);
      return streamRequest("/api/v3/concepts/clustered/stream?" + params, brief, onProgress);
    },
    editor: request
  };
})();
