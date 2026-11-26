"use strict";
importScripts("./runtime/pyodide.js");

async function initialize() {
  const manifest = await (await fetch("./manifest.json")).json();
  const python = await loadPyodide({indexURL: new URL("./runtime/", location.href).href});
  await python.loadPackage([...Object.keys(manifest.runtime_packages), ...manifest.engineering_wasm_packages]);
  python.FS.mkdirTree("/wheels");
  await Promise.all(manifest.pure_wheels.map(async name => {
    const response = await fetch("./wheels/" + name);
    if (!response.ok) throw Error("تعذّر تحميل مكتبة المحرك");
    python.FS.writeFile("/wheels/" + name, new Uint8Array(await response.arrayBuffer()));
  }));
  const response = await fetch("./engine.zip");
  if (!response.ok) throw Error("تعذّر تحميل المحرك");
  python.FS.writeFile("/engine.zip", new Uint8Array(await response.arrayBuffer()));
  python.runPython(`
import pathlib, site, sys, zipfile
for wheel in pathlib.Path('/wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site.getsitepackages()[0])
with zipfile.ZipFile('/engine.zip') as archive:
    archive.extractall('/project')
sys.path.insert(0, '/project')
from browser_customer.dispatch import dispatch
`);
  return python.globals.get("dispatch");
}

let ready;
self.onmessage = async ({data}) => {
  const {id, path, body, snapshot} = data;
  try {
    ready ??= initialize().catch(error => {
      ready = undefined;
      throw error;
    });
    const dispatch = await ready;
    const result = !path ? {status: 200, data: true} : JSON.parse(
      dispatch(path, JSON.stringify(body), snapshot, event => {
        postMessage({id, event: JSON.parse(event)});
      })
    );
    postMessage({id, result});
  } catch (error) {
    postMessage({id, error: String(error).trim().split("\n").slice(-6).join(" | ")});
  }
};
