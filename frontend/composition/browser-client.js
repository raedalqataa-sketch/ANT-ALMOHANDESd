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
    generate: (strategy, brief, _onProgress, options = {}) => {
      if (strategy !== "clustered") throw Error("مسار التكوين غير متاح");
      return request("/api/v3/concepts/clustered?first_floor="+Boolean(options.firstFloor), brief);
    },
    editor: request
  };
})();
