"""Assemble the customer journey and its Python runtime for static hosting."""
import argparse
import re
import shutil
import zipfile
from pathlib import Path

from lovable_integration.browser_dependencies import prepare_browser_dependencies
from mobile_probe.build_bundle import build as build_runtime

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
EXTRA_PURE = {
    "fastapi": "0.115.14",
    "starlette": "0.46.2",
    "anyio": "4.9.0",
    "sniffio": "1.3.1",
    "idna": "3.10",
}
ROUTES = re.compile(r"""(?<=["'`])/(?:composition|editor|facades|massing|assets)(?=[/?#"'\x60]|$)""")


def build(output, prefix):
    engine = output / "engine"
    build_runtime(engine, EXTRA_PURE, extra_runtime=("ssl",))
    manifest = engine / "manifest.json"
    prepare_browser_dependencies(engine / "runtime", engine / "wheels", manifest, manifest)
    (engine / "index.html").unlink()
    shutil.copyfile(HERE / "worker.js", engine / "worker.js")
    shutil.copyfile(HERE / "client.js", engine / "client.js")
    base = engine / "engine.zip"
    packed = engine / "customer.zip"
    runtime_data = {
        "constitution/architecture_v2/ANT_ALMOHANDES_UNIFIED_ARCH_RULES_V2.json",
        "constitution/saudi/national-2024.json",
        "constitution/saudi/residential-2024-extension.json",
    }
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in source.namelist():
            if name.startswith(("backend/", "frontend/")) or name in runtime_data:
                archive.writestr(name, source.read(name))
        archive.write(HERE / "dispatch.py", "browser_customer/dispatch.py")
        for folder in ("assl", "quality_review"):
            for file in sorted((ROOT / folder).rglob("*.py")):
                archive.write(file, file.relative_to(ROOT))
    packed.replace(base)

    frontend = ROOT / "frontend"
    for name in ("composition", "facades", "massing"):
        shutil.copytree(frontend / name, output / name, dirs_exist_ok=True)
    (output / "massing" / "render.html").unlink(missing_ok=True)
    editor = output / "editor"
    editor.mkdir(exist_ok=True)
    shutil.move(output / "composition" / "editor.html", editor / "index.html")
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copyfile(frontend / "Arabic.ttf", assets / "Arabic.ttf")
    shutil.copyfile(frontend / "FONT-LICENSE.txt", assets / "FONT-LICENSE.txt")

    for folder in ("composition", "editor", "facades", "massing"):
        for file in (output / folder).iterdir():
            if file.suffix not in (".html", ".js", ".mjs", ".css"):
                continue
            content = ROUTES.sub(lambda match: prefix + match.group(), file.read_text())
            if file.suffix == ".html":
                content = content.replace("الحساب الهندسي يجري على الخادم المحلي.", "الحساب الهندسي يجري داخل متصفحك.")
                content = content.replace('href="/"', f'href="{prefix}/composition/?strategy=clustered"')
                content = re.sub(r'<a\b[^>]*href="/generate/"[^>]*>.*?</a>', '', content)
                content = content.replace("<head>", f'<head><script src="{prefix}/engine/client.js"></script>')
            file.write_text(content)

    (output / ".nojekyll").touch()
    (output / "index.html").write_text(
        '<!doctype html><html lang="ar"><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0;url=./composition/?strategy=clustered">'
        '<a href="./composition/?strategy=clustered">أنت المهندس</a></html>'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    build(args.output.resolve(), args.prefix.rstrip("/"))
