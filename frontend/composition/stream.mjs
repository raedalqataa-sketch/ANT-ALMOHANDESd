export async function streamRequest(path, body, onProgress) {
  const response = await fetch(path,{
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  if (!response.ok || !response.body) throw Error("تعذر بدء العملية ("+response.status+")");
  const reader=response.body.pipeThrough(new TextDecoderStream()).getReader();
  let pending="", result;
  try {
    while (true) {
      const {done,value}=await reader.read();
      if (done) break;
      pending+=value;
      let end;
      while ((end=pending.indexOf("\n"))!==-1) {
        const event=JSON.parse(pending.slice(0,end));
        pending=pending.slice(end+1);
        if (event.error) throw Error(typeof event.error==="string"?event.error:JSON.stringify(event.error));
        if (event.percent!==undefined) onProgress?.(event);
        if (event.result!==undefined) result=event.result;
      }
    }
  } finally {
    await reader.cancel();
  }
  if (result===undefined) throw Error("انقطع الاتصال قبل وصول النتيجة.");
  return result;
}
