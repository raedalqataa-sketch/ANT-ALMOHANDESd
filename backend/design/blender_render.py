"""Local Cycles renderer for an immutable massing mesh and a selected camera."""
import base64
from collections import deque
import logging
import json
import os
from pathlib import Path
import re
import shutil
from subprocess import PIPE, STDOUT, Popen
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore, Timer

LOGGER = logging.getLogger(__name__)
SLOTS = BoundedSemaphore(1)
SAMPLE = re.compile(r"\bSample\s+(\d+)/\s*(\d+)")


def render_image(model, style_id, camera, progress):
    blender = shutil.which(os.environ.get("ANT_BLENDER_BIN", "blender"))
    if not blender:
        raise ValueError("يتطلب الرندر تثبيت Blender على الخادم المحلي.")
    style = next((style for style in model["styles"] if style["id"] == style_id), None)
    if style is None:
        raise ValueError("الطراز المختار غير متاح.")
    if not SLOTS.acquire(blocking=False):
        raise ValueError("توجد صورة قيد الرندر. أعد المحاولة بعد اكتمالها.")
    try:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scene, image = root/"scene.json", root/"render.png"
            scene.write_text(json.dumps({"faces":style["faces"],"camera":camera}))
            progress(12, "إعداد الخامات والإضاءة والكاميرا في Blender")
            threads = min(8, max(1, len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else os.cpu_count() or 1))
            command = [blender,"--background","--factory-startup","--threads",str(threads),
                       "--python-exit-code","1","--python",str(Path(__file__).with_name("cycles_scene.py")),
                       "--",str(scene),str(image)]
            with Popen(command, stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace") as process:
                timer = Timer(720, process.kill)
                timer.daemon = True
                timer.start()
                last = 12
                recent = deque(maxlen=15)
                try:
                    for line in process.stdout:
                        recent.append(line)
                        sample = SAMPLE.search(line)
                        if sample:
                            n, total = map(int,sample.groups())
                            percent = min(94, 18+int(76*n/max(1,total)))
                            if percent > last:
                                progress(percent, "حساب الإضاءة والخامات · "+str(n)+"/"+str(total))
                                last = percent
                        elif "Denois" in line and last < 95:
                            progress(95,"إزالة ضجيج الصورة")
                            last = 95
                    if process.wait() != 0 or not image.is_file():
                        LOGGER.error("Cycles render failed: %s","".join(recent))
                        raise ValueError("توقّف رندر Blender قبل إنشاء الصورة. تحقق من موارد الخادم وأعد المحاولة.")
                finally:
                    timer.cancel()
            progress(98,"تجهيز صورة PNG للتنزيل")
            return {"image":base64.b64encode(image.read_bytes()).decode("ascii"),
                    "width":3840,"height":2160,"style":style_id,
                    "revision":model["revision"],"camera":camera}
    finally:
        SLOTS.release()
