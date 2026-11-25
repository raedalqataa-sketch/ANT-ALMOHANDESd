"""Stream completed work milestones without blocking the ASGI event loop."""
import json
from queue import Queue
from threading import Thread

from fastapi.responses import StreamingResponse


def stream_work(operation):
    events = Queue()

    def progress(percent, detail):
        events.put({"percent": percent, "detail": detail})

    def execute():
        try:
            events.put({"result": operation(progress)})
        except Exception as error:
            events.put({"error": getattr(error, "detail", str(error))})
        finally:
            events.put(None)

    def stream():
        Thread(target=execute, daemon=True).start()
        while (event := events.get()) is not None:
            yield json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
