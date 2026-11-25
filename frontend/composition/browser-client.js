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
    prepare: async () => true,
    generate: async (strategy, brief, onProgress, options = {}) => {
      if (strategy !== "clustered") throw Error("مسار التكوين غير متاح");
      const {streamRequest} = await import("./stream.mjs");
      return streamRequest("/api/v3/concepts/clustered/stream?first_floor="+Boolean(options.firstFloor), brief, onProgress);
    },
    editor: request
  };
})();
