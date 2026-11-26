(() => {
  const workerURL = new URL("./worker.js", document.currentScript.src);
  const networkFetch = window.fetch.bind(window);
  const sessionPrefix = "ant-browser-editor:";
  const pending = new Map();
  let worker;
  let sequence = 0;

  function call(path, body, progress) {
    return new Promise((resolve, reject) => {
      if (!worker) {
        worker = new Worker(workerURL);
        worker.onerror = error => {
          for (const task of pending.values()) task.reject(Error(error.message));
          pending.clear();
          worker.terminate();
          worker = undefined;
        };
        worker.onmessage = ({data}) => {
          const task = pending.get(data.id);
          if (!task) return;
          if (data.event) {
            task.progress?.(data.event);
            return;
          }
          pending.delete(data.id);
          if (data.error) task.reject(Error(data.error));
          else task.resolve(data.result);
        };
      }
      const sid = body?.editor_revision?.session_id ?? path?.match(/\/sessions\/([a-f0-9]{32})/)?.[1];
      const snapshot = sid ? sessionStorage.getItem(sessionPrefix + sid) : null;
      const id = ++sequence;
      pending.set(id, {resolve, reject, progress});
      worker.postMessage({id, path, body, snapshot});
    }).then(reply => {
      if (reply.snapshot) {
        const key = sessionPrefix + reply.session;
        const saved = JSON.parse(sessionStorage.getItem(key) || "{}");
        sessionStorage.setItem(key, JSON.stringify({...saved, ...reply.snapshot}));
      }
      return reply;
    });
  }

  window.AntBrowserEngine = {prepare: () => call(null, null)};
  window.fetch = async (input, options) => {
    const url = new URL(input instanceof Request ? input.url : input, location.href);
    if (url.origin !== location.origin || !/^\/api\/(editor\/sessions|v3\/concepts\/)/.test(url.pathname)) {
      return networkFetch(input, options);
    }
    const path = url.pathname + url.search;
    const body = options?.body ? JSON.parse(options.body) : null;
    if (url.pathname.endsWith("/stream")) {
      const encoder = new TextEncoder();
      let cancelled = false;
      return new Response(new ReadableStream({
        start(controller) {
          const send = event => {
            if (!cancelled) controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
          };
          call(path, body, send).then(reply => {
            send(reply.status === 200 ? {result: reply.data} : {error: reply.data.detail});
          }, error => send({error: error.message})).finally(() => {
            if (!cancelled) controller.close();
          });
        },
        cancel() { cancelled = true; }
      }));
    }
    const reply = await call(path, body);
    return Response.json(reply.data, {status: reply.status});
  };

  document.addEventListener("click", async event => {
    const link = event.target.closest('a[download][href^="/api/editor/"]');
    if (!link) return;
    event.preventDefault();
    try {
      const reply = await call(new URL(link.href).pathname, null);
      if (reply.status !== 200) throw Error(reply.data.detail);
      const bytes = Uint8Array.from(atob(reply.data.bytes), char => char.charCodeAt(0));
      const href = URL.createObjectURL(new Blob([bytes]));
      const download = document.createElement("a");
      download.href = href;
      download.download = reply.data.filename;
      download.click();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
    } catch (error) {
      alert("تعذّر تنزيل الملف: " + error.message);
    }
  });
})();
