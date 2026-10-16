"""Build the Windows x64 portable app using the current isolated interpreter."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from world_builder.desktop import VERSION

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='WorldBuilder')
    args=parser.parse_args()
    if not args.name.replace('-','').replace('_','').isalnum():parser.error('Invalid application name')
    if sys.platform != "win32" or platform.architecture()[0] != "64bit":
        raise SystemExit("Build on 64-bit Windows Python")
    target = ROOT / 'dist' / args.name
    if target.exists():
        raise SystemExit("dist/WorldBuilder already exists; preserve or rename the previous build first")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
               "--name", args.name, "--paths", str(ROOT / "src"),
               "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build/desktop"),
               "--specpath", str(ROOT / "build"), "--icon", str(ROOT / "desktop/world-builder.ico"),
               "--collect-all", "webview", "--hidden-import", "_socket", "--exclude-module", "PyQt5", "--exclude-module", "PySide6"]
    resources = [("web", "web"), ("schemas", "schemas"), ("storage/migrations", "storage/migrations"),
                 ("config/agents.example.json", "config"), ("examples/agent_scene.responses.json", "examples"),
                 ("desktop/world-builder.ico", "desktop")]
    resources.extend((p,str(Path(p).parent)) for p in ('config/agents.deepseek-nature046.json','examples/nature047_reference.json','examples/nature046_recipes.json'))
    resources.extend((p,p) for p in ('skills/world-nature-046','skills/world-client-047','settings/arcane_medieval'))
    resources.extend((f"skills/world-agent-{stage}", f"skills/world-agent-{stage}") for stage in "abcdef")
    for source, destination in resources:
        command.extend(["--add-data", f"{ROOT / source};{destination}"])
    command.append(str(ROOT / "tools/run_desktop.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    shutil.copyfile(ROOT / "desktop/README.txt", target / "README.txt")
    archive = Path(shutil.make_archive(str(ROOT / f'dist/{args.name}-{VERSION}-win-x64'), "zip", ROOT / "dist", args.name))
    report = {"version":VERSION, "python":sys.version, "archive":archive.name,
              "bytes":archive.stat().st_size, "sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}
    (ROOT / f'dist/build-info-{args.name}.json').write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
