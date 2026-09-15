"""Build the isolated TWINKLE PNG interpolation comparison pilot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

CANDIDATES = ("A", "B")
DENSITIES = (192, 288)
FRAME_COUNT = 96
ORBIT_DURATION_MS = 8_000
ANGLE_STEP_DEGREES = 3.75
EXPECTED_BLEND_SHA256 = "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
STAGE4_BRANCH = "codex/twinkle-hotspot-page-revision"
STAGE4_HEAD = "4b8f43e4ca5cf636432392d330c51e1faa8d2d78"
STAGE4_RELATIVE_OUTPUT = Path(
    "output/.twinkle-stage4-orbit-c360-f96-20260829/orbit-c360-f96-r1"
)
REPRESENTATIVE_INTERVALS = (
    {
        "id": "outline-hole-reflection-dual",
        "startFrame": 7,
        "endFrame": 8,
        "reasons": ["largest-pixel-change", "outline", "hole", "reflection", "two-hotspots"],
    },
    {
        "id": "visible-hidden-boundary",
        "startFrame": 8,
        "endFrame": 9,
        "reasons": ["hotspot-visible-hidden-boundary", "high-luminance-change"],
    },
    {
        "id": "hole-rod-reflection-single",
        "startFrame": 64,
        "endFrame": 65,
        "reasons": ["high-pixel-change", "hole", "thin-rod", "reflection", "single-hotspot"],
    },
    {
        "id": "thin-edge-small-component-single",
        "startFrame": 78,
        "endFrame": 79,
        "reasons": ["largest-edge-change", "thin-edge", "small-component", "single-hotspot"],
    },
    {
        "id": "cyclic-seam-dual",
        "startFrame": 95,
        "endFrame": 0,
        "reasons": ["095-to-000-seam", "internal-gap", "reflection", "two-hotspots"],
    },
)


class PilotValidationError(ValueError):
    """Raised when a pilot boundary or source contract is violated."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _json_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PilotValidationError(f"cannot import authority module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_fixed_pilot_module(repo: Path):
    return _load_module(
        Path(repo) / "scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py",
        "twinkle_fixed_orbit_authority",
    )


def validate_output_root(repo: Path, output_root: Path) -> Path:
    expected = (Path(repo).resolve() / "output/twinkle-stage5-png-interpolation-pilot").resolve()
    actual = Path(output_root).resolve()
    if actual != expected:
        raise PilotValidationError(f"PNG interpolation output must be exactly {expected}")
    return actual


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def registered_worktree_for_branch(repo: Path, branch: str) -> Path:
    records = []
    current = {}
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    expected = f"refs/heads/{branch}"
    matches = [Path(record["worktree"]).resolve() for record in records if record.get("branch") == expected]
    if len(matches) != 1:
        raise PilotValidationError(f"expected one Git-registered worktree for {branch}")
    return matches[0]


def stage4_source_paths(repo: Path, stage4_repo: Path) -> dict:
    repo = Path(repo).resolve()
    stage4_repo = Path(stage4_repo).resolve()
    if _git(stage4_repo, "branch", "--show-current") != STAGE4_BRANCH:
        raise PilotValidationError("Stage 4 branch drift")
    if _git(stage4_repo, "rev-parse", "HEAD") != STAGE4_HEAD:
        raise PilotValidationError("Stage 4 HEAD drift")
    registered = _git(repo, "worktree", "list", "--porcelain")
    if f"worktree {stage4_repo.as_posix()}" not in registered:
        raise PilotValidationError("Stage 4 worktree is not Git-registered")
    manifest = stage4_repo / STAGE4_RELATIVE_OUTPUT / "orbit-c360-f96-manifest.json"
    script = stage4_repo / "scripts/build_twinkle_stage4_orbit.py"
    stage1 = json.loads(
        (repo / "registry/twinkle/stage5-source-manifests/stage1-camera-board.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = Path(stage1["candidateBlend"]["path"]).resolve()
    if not manifest.is_file() or not script.is_file() or not candidate.is_file():
        raise PilotValidationError("Stage 4 source authority is missing")
    if sha256(candidate) != EXPECTED_BLEND_SHA256:
        raise PilotValidationError("Stage 4 candidate blend drift")
    return {
        "repo": stage4_repo,
        "manifest": manifest,
        "script": script,
        "candidateBlend": candidate,
    }


def _source_snapshot(paths: dict) -> dict:
    result = {}
    for key in ("manifest", "script", "candidateBlend"):
        path = paths[key]
        stat = path.stat()
        result[key] = {
            "path": str(path),
            "sha256": sha256(path),
            "bytes": stat.st_size,
            "mtimeNs": stat.st_mtime_ns,
        }
    return result


def load_authority(repo: Path) -> dict:
    fixed = load_fixed_pilot_module(repo)
    return fixed.load_authority(Path(repo))


def sample_points(authority: dict) -> list[dict]:
    points = []
    fractions = ((192, 1, 2), (288, 1, 3), (288, 2, 3))
    for interval in REPRESENTATIVE_INTERVALS:
        start = interval["startFrame"]
        end = interval["endFrame"]
        start_angle = authority["frames"][start]["angleDegrees"]
        end_angle = authority["frames"][end]["angleDegrees"]
        delta = (end_angle - start_angle) % 360.0
        for density, numerator, denominator in fractions:
            fraction = numerator / denominator
            angle = (start_angle + delta * fraction) % 360.0
            points.append(
                {
                    "id": f"{start:03d}-{end:03d}-{density}-{numerator}of{denominator}",
                    "intervalId": interval["id"],
                    "startFrame": start,
                    "endFrame": end,
                    "density": density,
                    "fraction": f"{numerator}/{denominator}",
                    "fractionValue": fraction,
                    "angleDegrees": angle,
                    "candidateIds": ["A", "B"],
                }
            )
    return points


def _pixel_contract(path: Path) -> dict:
    from PIL import Image

    with Image.open(path) as image:
        alpha = image.getchannel("A") if image.mode == "RGBA" else None
        return {
            "format": image.format,
            "mode": image.mode,
            "size": list(image.size),
            "alphaExtrema": list(alpha.getextrema()) if alpha is not None else None,
            "srgb": "srgb" in image.info,
            "gamma": image.info.get("gamma"),
        }


def _pixel_sha(path: Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest().upper()


def _pixel_comparison(left: Path, right: Path) -> dict:
    from PIL import Image, ImageChops, ImageStat

    with Image.open(left) as left_image, Image.open(right) as right_image:
        left_rgba = left_image.convert("RGBA")
        right_rgba = right_image.convert("RGBA")
        difference = ImageChops.difference(left_rgba, right_rgba)
        extrema = difference.getextrema()
        different = sum(
            1 for pixel in difference.get_flattened_data() if pixel != (0, 0, 0, 0)
        )
        total = left_rgba.width * left_rgba.height
        return {
            "differentPixelCount": different,
            "differentPixelFraction": different / total,
            "maximumChannelDelta": max(high for _low, high in extrema),
            "meanAbsoluteChannelDelta": ImageStat.Stat(difference).mean,
        }


def _formal_snapshot(repo: Path) -> dict:
    registry_path = Path(repo) / "registry/twinkle/stage5-runtime-assets.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = registry["runtimeInventory"]["files"]
    actual = []
    for record in records:
        path = Path(repo) / record["targetPath"]
        if not path.is_file() or sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise PilotValidationError(f"formal asset drift: {record['targetPath']}")
        actual.append(
            {"path": record["targetPath"], "sha256": record["sha256"], "bytes": record["bytes"]}
        )
    return {
        "registrySha256": sha256(registry_path),
        "inventorySha256": _json_sha(actual),
        "fileCount": len(actual),
    }


def blender_command(
    blender: Path,
    candidate: Path,
    builder: Path,
    output_root: Path,
    stage4_repo: Path,
    mode: str,
    points: Path,
) -> list[str]:
    return [
        str(Path(blender).resolve()),
        "--background",
        str(Path(candidate).resolve()),
        "--python-exit-code",
        "17",
        "--python",
        str(Path(builder).resolve()),
        "--",
        "--blender-worker",
        mode,
        "--worker-output",
        str(Path(output_root).resolve()),
        "--worker-points",
        str(Path(points).resolve()),
        "--worker-stage4-repo",
        str(Path(stage4_repo).resolve()),
    ]


def ffmpeg_command(
    ffmpeg: Path, input_pattern: Path, output_pattern: Path, density: int
) -> list[str]:
    if density == 192:
        select = "select=eq(n\\,3)"
        frames = "1"
    elif density == 288:
        select = "select=eq(n\\,4)+eq(n\\,5)"
        frames = "2"
    else:
        raise PilotValidationError("unsupported pilot density")
    filter_graph = (
        f"minterpolate=fps={density / 8:g}:mi_mode=mci:mc_mode=aobmc:"
        f"me_mode=bilat:me=epzs:mb_size=8:vsbmc=1,{select},format=rgba"
    )
    return [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "verbose",
        "-y",
        "-framerate",
        "12",
        "-i",
        str(input_pattern),
        "-vf",
        filter_graph,
        "-fps_mode",
        "passthrough",
        "-frames:v",
        frames,
        "-pix_fmt",
        "rgba",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "iec61966-2-1",
        "-colorspace",
        "rgb",
        str(output_pattern),
    ]


def _run(command: list[str], *, cwd: Path | None = None) -> dict:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsedSeconds": time.perf_counter() - started,
    }


def _assemble_baseline(output_root: Path, authority: dict) -> list[dict]:
    root = output_root / "baseline"
    root.mkdir(parents=True, exist_ok=True)
    indices = sorted(
        {value for interval in REPRESENTATIVE_INTERVALS for value in (interval["startFrame"], interval["endFrame"])}
    )
    records = []
    for index in indices:
        source = authority["frames"][index]
        target = root / f"frame-{index:03d}.png"
        shutil.copyfile(source["path"], target)
        if sha256(target) != source["sha256"] or target.stat().st_size != source["bytes"]:
            raise PilotValidationError("baseline copy drift")
        records.append(
            {
                "index": index,
                "angleDegrees": source["angleDegrees"],
                "src": target.relative_to(output_root).as_posix(),
                "sha256": source["sha256"],
                "bytes": source["bytes"],
                "hotspots": source["hotspots"],
            }
        )
    return records


def _run_blender_candidate(
    repo: Path,
    output_root: Path,
    authority: dict,
    sources: dict,
    blender: Path,
    points: list[dict],
) -> tuple[dict, list[dict]]:
    result = {
        "method": "authoritative-blender-real-render",
        "status": "failed",
        "formalUsable": False,
        "recommended": False,
        "renderSettings": {"resolution": [640, 450], "samples": 64, "format": "PNG", "mode": "RGBA"},
        "failureEvidence": [],
    }
    worker_points = output_root / "work/blender-points.json"
    _write_json(worker_points, points)
    builder = Path(__file__).resolve()
    control = _run(
        blender_command(
            blender,
            sources["candidateBlend"],
            builder,
            output_root,
            sources["repo"],
            "control",
            worker_points,
        )
    )
    _write_json(output_root / "evidence/blender-control-command.json", control)
    result["controlElapsedSeconds"] = control["elapsedSeconds"]
    if control["exitCode"] != 0:
        result["failureEvidence"].append("Blender control render command failed")
        return result, []
    control_path = output_root / "evidence/blender-control-frame-008.png"
    authority_path = authority["frames"][8]["path"]
    result["controlPixelSha256"] = _pixel_sha(control_path)
    result["authorityPixelSha256"] = _pixel_sha(authority_path)
    result["controlPixelExact"] = result["controlPixelSha256"] == result["authorityPixelSha256"]
    result["controlPixelContract"] = _pixel_contract(control_path)
    control_audit = json.loads(
        (output_root / "work/blender-worker-results.json").read_text(encoding="utf-8")
    )["frames"][0]
    stage4_manifest = json.loads(sources["manifest"].read_text(encoding="utf-8"))
    expected_camera = stage4_manifest["frames"][8]["camera"]
    result["controlCameraExact"] = (
        control_audit["cameraLocation"] == expected_camera["location"]
        and control_audit["cameraRotationQuaternion"]
        == expected_camera["rotationQuaternion"]
    )
    result["controlPixelComparison"] = _pixel_comparison(control_path, authority_path)
    result["controlSceneCompositionPassed"] = (
        result["controlCameraExact"]
        and result["controlPixelContract"] == _pixel_contract(authority_path)
        and result["controlPixelComparison"]["maximumChannelDelta"] <= 1
        and result["controlPixelComparison"]["differentPixelFraction"] <= 0.0002
    )
    if not result["controlSceneCompositionPassed"]:
        result["failureEvidence"].append("Blender control render does not exactly reproduce authority pixels")
        return result, []
    samples = _run(
        blender_command(
            blender,
            sources["candidateBlend"],
            builder,
            output_root,
            sources["repo"],
            "samples",
            worker_points,
        )
    )
    _write_json(output_root / "evidence/blender-sample-command.json", samples)
    result["sampleElapsedSeconds"] = samples["elapsedSeconds"]
    if samples["exitCode"] != 0:
        result["failureEvidence"].append("Blender sample render command failed")
        return result, []
    audit_path = output_root / "work/blender-worker-results.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    frames = []
    for record in audit["frames"]:
        path = output_root / record["src"]
        point = next(point for point in points if point["id"] == record["sampleId"])
        frames.append(
            {
                **point,
                **record,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "hotspots": authority["frames"][point["startFrame"]]["hotspots"],
                "sourceFrames": [point["startFrame"], point["endFrame"]],
            }
        )
    if len(frames) != 15 or audit["sourceRestored"] is not True:
        result["failureEvidence"].append("Blender bounded render or restoration audit failed")
        return result, frames
    result["status"] = "passed"
    result["totalElapsedSeconds"] = control["elapsedSeconds"] + samples["elapsedSeconds"]
    return result, frames


def _run_ffmpeg_candidate(
    output_root: Path, authority: dict, ffmpeg: Path, points: list[dict]
) -> tuple[dict, list[dict]]:
    version = _run([str(ffmpeg), "-version"])
    result = {
        "method": "ffmpeg-minterpolate-mci",
        "status": "failed",
        "formalUsable": False,
        "recommended": False,
        "ffmpegVersion": version["stdout"].splitlines()[0] if version["stdout"] else "",
        "parameters": [],
        "failureEvidence": [],
    }
    frames = []
    started = time.perf_counter()
    for interval in REPRESENTATIVE_INTERVALS:
        start, end = interval["startFrame"], interval["endFrame"]
        previous, following = (start - 1) % 96, (end + 1) % 96
        input_root = output_root / "work/ffmpeg" / interval["id"] / "inputs"
        input_root.mkdir(parents=True, exist_ok=True)
        for ordinal, index in enumerate((previous, start, end, following)):
            shutil.copyfile(authority["frames"][index]["path"], input_root / f"{ordinal:03d}.png")
        for density in DENSITIES:
            selected = [
                point for point in points if point["intervalId"] == interval["id"] and point["density"] == density
            ]
            candidate_root = output_root / "candidates/B" / str(density)
            candidate_root.mkdir(parents=True, exist_ok=True)
            output_pattern = candidate_root / f"{start:03d}-{end:03d}-%02d.png"
            command = ffmpeg_command(ffmpeg, input_root / "%03d.png", output_pattern, density)
            result["parameters"].append(command[command.index("-vf") + 1])
            run = _run(command)
            evidence = output_root / "evidence/ffmpeg" / f"{interval['id']}-{density}.json"
            _write_json(evidence, run)
            produced = sorted(candidate_root.glob(f"{start:03d}-{end:03d}-*.png"))
            if run["exitCode"] != 0 or len(produced) != len(selected):
                result["failureEvidence"].append(
                    f"{interval['id']}/{density} command or output-count failure"
                )
                result["totalElapsedSeconds"] = time.perf_counter() - started
                return result, frames
            for point, path in zip(selected, produced):
                contract = _pixel_contract(path)
                contract_passed = contract == {
                    "format": "PNG",
                    "mode": "RGBA",
                    "size": [640, 450],
                    "alphaExtrema": [255, 255],
                    "srgb": True,
                    "gamma": 0.45455,
                }
                frames.append(
                    {
                        **point,
                        "src": path.relative_to(output_root).as_posix(),
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                        "elapsedSeconds": run["elapsedSeconds"] / len(produced),
                        "sourceFrames": [start, end],
                        "ffmpegFilter": command[command.index("-vf") + 1],
                        "pixelContract": contract,
                        "pixelContractPassed": contract_passed,
                        "hotspots": authority["frames"][start]["hotspots"],
                    }
                )
                if not contract_passed:
                    result["failureEvidence"].append(
                        f"{point['id']} changed PNG size/alpha/color contract: {contract}"
                    )
                    result["totalElapsedSeconds"] = time.perf_counter() - started
                    return result, frames
    result["status"] = "passed"
    result["pixelContract"] = {
        "format": "PNG",
        "mode": "RGBA",
        "size": [640, 450],
        "alphaExtrema": [255, 255],
        "srgb": True,
        "gamma": 0.45455,
    }
    result["totalElapsedSeconds"] = time.perf_counter() - started
    return result, frames


PILOT_HTML = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>TWINKLE PNG 补帧 A/B Pilot</title><link rel="stylesheet" href="pilot.css"></head><body>
<header><h1>TWINKLE PNG 补帧固定样本</h1><p>仅比较固定代表区间；不构成正式方案选择。</p><label>区间 <select id="interval"></select></label><button id="play" type="button">同步播放一次</button><output id="status">加载中</output></header>
<main id="grid">
<section class="variant" data-variant="baseline"><h2>原始 96 / 12 fps</h2><div class="stage"></div></section>
<section class="variant" data-variant="A-192"><h2>A / 192 / 24 fps</h2><div class="stage"></div></section>
<section class="variant" data-variant="A-288"><h2>A / 288 / 36 fps</h2><div class="stage"></div></section>
<section class="variant" data-variant="B-192"><h2>B / 192 / 24 fps</h2><div class="stage"></div></section>
<section class="variant" data-variant="B-288"><h2>B / 288 / 36 fps</h2><div class="stage"></div></section>
</main><script src="pilot.js"></script></body></html>
'''


PILOT_CSS = r'''
:root{color-scheme:dark;--bg:#0c0f12;--panel:#151a20;--line:rgba(255,255,255,.16);--text:#f6f7f8;--muted:#aab3bc}*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.4 system-ui,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}header{position:sticky;z-index:5;top:0;padding:12px 18px;border-bottom:1px solid var(--line);background:rgba(12,15,18,.94)}h1{margin:0;font-size:18px}header p{display:inline;margin:0 18px;color:var(--muted)}button,select{margin-left:8px;padding:6px 9px}#status{margin-left:12px;color:var(--muted)}#grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:12px}.variant{min-width:0;border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden}.variant h2{margin:0;padding:8px 10px;font-size:13px}.stage{position:relative;aspect-ratio:640/450;overflow:hidden;touch-action:pan-y;cursor:grab;background:#eee}.stage[data-held="true"]{cursor:grabbing}.stage img{display:block;width:100%;height:100%;object-fit:contain;pointer-events:none}.hotspot[hidden]{display:none!important}.hotspot{position:absolute;width:30px;height:30px;transform:translate(-50%,-50%);border:0;background:transparent;color:#fff;padding:0}.hotspot-ring{position:absolute;inset:6px;border:1.5px solid currentColor;border-radius:50%;background:rgba(12,15,18,.36)}.hotspot-ring::after{content:"";position:absolute;inset:4px;border-radius:50%;background:currentColor}.hotspot-label{position:absolute;left:27px;top:50%;transform:translate(0,-50%);padding:5px 9px;border:1px solid rgba(255,255,255,.13);border-radius:5px;background:rgba(18,22,27,.78);color:#fff;font-size:12px;font-weight:600;white-space:nowrap;opacity:1;pointer-events:none}@media(max-width:900px){#grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
'''.strip()


PILOT_JS = r'''
'use strict';
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const variants=['baseline','A-192','A-288','B-192','B-288'];
const names={dual_channel_collection_optics_chamber:'双通道采集光学舱',dual_channel_condenser_lens_assembly:'聚光镜组件'};
const state={manifest:null,intervalIndex:0,phase:0,playing:false,last:null,speed:1,held:false,dragging:false,pointerId:null,startX:0,startY:0,startPhase:0,history:[],errors:[]};
const select=document.querySelector('#interval'),status=document.querySelector('#status');
function sequence(key,interval){const baseline=new Map(state.manifest.baselineFrames.map(x=>[x.index,x]));const start=baseline.get(interval.startFrame),end=baseline.get(interval.endFrame),first={...start,fractionValue:0},last={...end,fractionValue:1};if(key==='baseline')return [first,last];const [candidate,density]=key.split('-');const frames=state.manifest.candidates[candidate].frames.filter(x=>x.intervalId===interval.id&&x.density===Number(density));return [first,...frames,last].sort((a,b)=>a.fractionValue-b.fractionValue);}
function frameAt(items,phase){let selected=items[0];for(const item of items){if((item.fractionValue||0)<=phase+1e-9)selected=item;}return selected;}
function hotspotMarkup(stage){for(const unit of Object.keys(names)){const button=document.createElement('button');button.className='hotspot';button.dataset.unit=unit;button.innerHTML='<span class="hotspot-ring"></span><span class="hotspot-label">'+names[unit]+'</span>';stage.append(button);}}
function render(){if(!state.manifest)return;const interval=state.manifest.representativeIntervals[state.intervalIndex];for(const key of variants){const section=document.querySelector('[data-variant="'+key+'"]'),stage=section.querySelector('.stage');let image=stage.querySelector('img');if(!image){image=document.createElement('img');stage.prepend(image);hotspotMarkup(stage);}const record=frameAt(sequence(key,interval),state.phase);if(record){image.src=record.src;for(const button of stage.querySelectorAll('.hotspot')){const h=record.hotspots[button.dataset.unit],visible=h.status==='visible'&&h.eligible===true;button.hidden=!visible;button.style.left=(h.projection[0]*100)+'%';button.style.top=(h.projection[1]*100)+'%';}}}document.body.dataset.phase=state.phase.toFixed(6);status.textContent=interval.startFrame.toString().padStart(3,'0')+'→'+interval.endFrame.toString().padStart(3,'0')+' · '+Math.round(state.speed*100)+'%';}
function tick(now){if(state.last===null)state.last=now;const delta=Math.min(100,Math.max(0,now-state.last));state.last=now;if(state.playing&&!reduced.matches&&!state.held){state.phase+=delta/83.3333333333*state.speed;if(state.phase>=1){state.phase=1;state.playing=false;}render();state.history.push({time:now,phase:state.phase,sources:variants.map(k=>frameAt(sequence(k,state.manifest.representativeIntervals[state.intervalIndex]),state.phase)?.src||null)});}requestAnimationFrame(tick);}
function setIntervalIndex(index){state.intervalIndex=Math.max(0,Math.min(state.manifest.representativeIntervals.length-1,index));state.phase=0;state.playing=false;select.value=String(state.intervalIndex);render();}
function setPhase(value){state.phase=Math.max(0,Math.min(1,Number(value)));state.playing=false;render();}
function playOnce(){state.phase=0;state.playing=!reduced.matches;state.last=performance.now();state.history=[];render();}
select.addEventListener('change',()=>setIntervalIndex(Number(select.value)));document.querySelector('#play').addEventListener('click',playOnce);
for(const stage of document.querySelectorAll('.stage')){stage.dataset.held='false';stage.addEventListener('pointerdown',event=>{if(event.button!==0||state.pointerId!==null)return;state.pointerId=event.pointerId;state.held=true;state.dragging=false;state.startX=event.clientX;state.startY=event.clientY;state.startPhase=state.phase;stage.setPointerCapture(event.pointerId);stage.dataset.held='true';state.speed=0;render();});stage.addEventListener('pointermove',event=>{if(event.pointerId!==state.pointerId)return;const dx=event.clientX-state.startX,dy=event.clientY-state.startY;if(!state.dragging&&Math.hypot(dx,dy)>6)state.dragging=true;if(state.dragging){event.preventDefault();state.phase=Math.max(0,Math.min(1,state.startPhase+dx/stage.clientWidth));render();}});const release=event=>{if(event.pointerId!==state.pointerId)return;state.pointerId=null;state.held=false;state.speed=1;stage.dataset.held='false';render();};stage.addEventListener('pointerup',release);stage.addEventListener('pointercancel',release);stage.addEventListener('lostpointercapture',release);stage.addEventListener('pointerover',event=>{if(event.target.closest('.hotspot')){state.speed=.3;render();}});stage.addEventListener('pointerout',event=>{if(!event.relatedTarget?.closest?.('.hotspot')&&!state.held){state.speed=1;render();}});stage.addEventListener('focusin',event=>{if(event.target.closest('.hotspot')){state.speed=.3;render();}});stage.addEventListener('focusout',()=>{if(!state.held){state.speed=1;render();}});}
fetch('pilot-manifest.json').then(r=>{if(!r.ok)throw new Error('manifest '+r.status);return r.json();}).then(manifest=>{state.manifest=manifest;manifest.representativeIntervals.forEach((item,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=item.startFrame.toString().padStart(3,'0')+'→'+item.endFrame.toString().padStart(3,'0')+' · '+item.id;select.append(option);});setIntervalIndex(0);status.textContent='ready';}).catch(error=>{state.errors.push(error.message);status.textContent='resource failure';console.error(error);});
reduced.addEventListener('change',()=>{state.playing=false;state.phase=0;render();});
window.__twinkleInterpolationPilot={snapshot:()=>({ready:!!state.manifest,intervalIndex:state.intervalIndex,phase:state.phase,playing:state.playing,speed:state.speed,held:state.held,dragging:state.dragging,reducedMotion:reduced.matches,mode:reduced.matches?'static-authoritative':'motion',errors:[...state.errors]}),setInterval:setIntervalIndex,setPhase,playOnce,history:()=>state.history.map(x=>({...x}))};
requestAnimationFrame(tick);
'''.strip()


def _write_page(output_root: Path) -> None:
    (output_root / "index.html").write_text(PILOT_HTML, encoding="utf-8")
    (output_root / "pilot.css").write_text(PILOT_CSS + "\n", encoding="utf-8")
    (output_root / "pilot.js").write_text(PILOT_JS + "\n", encoding="utf-8")


def build_pilot(
    repo: Path,
    output_root: Path,
    stage4_repo: Path,
    blender: Path,
    ffmpeg: Path,
) -> dict:
    repo = Path(repo).resolve()
    output_root = validate_output_root(repo, output_root)
    if (output_root / "pilot-manifest.json").exists():
        raise FileExistsError(f"refusing to overwrite completed pilot: {output_root}")
    red = output_root / "evidence/red-evidence.json"
    if not red.is_file():
        raise PilotValidationError("correct RED evidence must exist before implementation run")
    sources = stage4_source_paths(repo, stage4_repo)
    source_before = _source_snapshot(sources)
    formal_before = _formal_snapshot(repo)
    authority = load_authority(repo)
    points = sample_points(authority)
    output_root.mkdir(parents=True, exist_ok=True)
    baseline = _assemble_baseline(output_root, authority)
    _write_json(output_root / "representative-intervals.json", REPRESENTATIVE_INTERVALS)

    a_result, a_frames = _run_blender_candidate(
        repo, output_root, authority, sources, Path(blender), points
    )
    b_result, b_frames = _run_ffmpeg_candidate(output_root, authority, Path(ffmpeg), points)

    source_after = _source_snapshot(sources)
    formal_after = _formal_snapshot(repo)
    source_protection = {
        "before": source_before,
        "after": source_after,
        "unchanged": source_before == source_after,
    }
    formal_protection = {
        "registryBefore": formal_before["registrySha256"],
        "registryAfter": formal_after["registrySha256"],
        "formalInventoryBefore": formal_before["inventorySha256"],
        "formalInventoryAfter": formal_after["inventorySha256"],
        "formalFileCount": formal_before["fileCount"],
        "formalWrites": 0,
    }
    if not source_protection["unchanged"] or formal_before != formal_after:
        raise PilotValidationError("protected source or formal assets changed during pilot")

    manifest = {
        "schema": "twinkle-stage5-png-interpolation-pilot-v1",
        "orbit": {"frameCount": 96, "durationMs": 8000, "direction": "forward", "seam": "095->000"},
        "representativeIntervals": list(REPRESENTATIVE_INTERVALS),
        "samplePoints": points,
        "baselineFrames": baseline,
        "candidates": {
            "A": {"status": a_result["status"], "frames": a_frames},
            "B": {"status": b_result["status"], "frames": b_frames},
        },
        "hotspotRule": "intermediate-holds-previous-authoritative-frame-without-projection-interpolation",
        "mobileLabelOverlapDeferred": True,
    }
    results = {
        "schema": "twinkle-stage5-png-interpolation-machine-results-v1",
        "machinePassed": a_result["status"] == "passed" and b_result["status"] in {"passed", "failed"},
        "representativeIntervalIds": [record["id"] for record in REPRESENTATIVE_INTERVALS],
        "candidates": {"A": a_result, "B": b_result},
        "sourceProtection": source_protection,
        "formalProtection": formal_protection,
        "authoritative96FrameShaBytesUnchanged": True,
        "generatedCompleteSequence": False,
        "formalIntegrationAuthorized": False,
        "formalSelectionMade": False,
        "browserAcceptancePending": True,
        "mobileLabelOverlapDeferred": True,
    }
    _write_json(output_root / "pilot-manifest.json", manifest)
    _write_json(output_root / "machine-results.json", results)
    _write_page(output_root)
    return results


def refresh_a_candidate(
    repo: Path, output_root: Path, stage4_repo: Path, blender: Path
) -> dict:
    """Re-run only the failed real-render gate without touching valid B evidence."""
    repo = Path(repo).resolve()
    output_root = validate_output_root(repo, output_root)
    manifest_path = output_root / "pilot-manifest.json"
    results_path = output_root / "machine-results.json"
    if not manifest_path.is_file() or not results_path.is_file():
        raise PilotValidationError("A refresh requires an existing bounded pilot result")
    sources = stage4_source_paths(repo, stage4_repo)
    source_before = _source_snapshot(sources)
    formal_before = _formal_snapshot(repo)
    authority = load_authority(repo)
    points = sample_points(authority)
    a_result, a_frames = _run_blender_candidate(
        repo, output_root, authority, sources, Path(blender), points
    )
    if source_before != _source_snapshot(sources) or formal_before != _formal_snapshot(repo):
        raise PilotValidationError("protected source changed during A refresh")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    manifest["candidates"]["A"] = {"status": a_result["status"], "frames": a_frames}
    results["candidates"]["A"] = a_result
    results["machinePassed"] = a_result["status"] == "passed" and results["candidates"]["B"][
        "status"
    ] in {"passed", "failed"}
    _write_json(manifest_path, manifest)
    _write_json(results_path, results)
    return results


def build_visual_evidence(repo: Path, output_root: Path) -> dict:
    """Create bounded same-time A/B comparisons for the 15 fixed samples."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

    output_root = validate_output_root(repo, output_root)
    manifest = json.loads((output_root / "pilot-manifest.json").read_text(encoding="utf-8"))
    by_candidate = {
        candidate: {record["id"]: record for record in manifest["candidates"][candidate]["frames"]}
        for candidate in CANDIDATES
    }
    expected = {record["id"] for record in manifest["samplePoints"]}
    if any(set(records) != expected for records in by_candidate.values()):
        raise PilotValidationError("same-time comparison requires all 15 A/B samples")
    comparisons = output_root / "comparisons"
    comparisons.mkdir(parents=True, exist_ok=True)
    metrics = []
    for point in manifest["samplePoints"]:
        sample_id = point["id"]
        a_record, b_record = by_candidate["A"][sample_id], by_candidate["B"][sample_id]
        a_path, b_path = output_root / a_record["src"], output_root / b_record["src"]
        with Image.open(a_path) as a_source, Image.open(b_path) as b_source:
            a = a_source.convert("RGBA")
            b = b_source.convert("RGBA")
            difference = ImageChops.difference(a, b)
            boosted = difference.point(lambda value: min(255, value * 4))
            canvas = Image.new("RGBA", (1920, 480), (12, 15, 18, 255))
            canvas.paste(a, (0, 30))
            canvas.paste(b, (640, 30))
            canvas.paste(boosted, (1280, 30))
            draw = ImageDraw.Draw(canvas)
            draw.text((8, 8), f"A real render | {sample_id} | {point['angleDegrees']:.6f} deg", fill="white")
            draw.text((648, 8), "B FFmpeg motion interpolation", fill="white")
            draw.text((1288, 8), "absolute difference x4", fill="white")
            comparison_path = comparisons / f"{sample_id}.png"
            canvas.save(comparison_path)
            difference_path = comparisons / "differences" / f"{sample_id}.png"
            difference_path.parent.mkdir(parents=True, exist_ok=True)
            difference.save(difference_path)
            edge_a = a.convert("RGB").filter(ImageFilter.FIND_EDGES)
            edge_b = b.convert("RGB").filter(ImageFilter.FIND_EDGES)
            edge_difference = ImageChops.difference(edge_a, edge_b)
            stats = ImageStat.Stat(difference)
            extrema = difference.getextrema()
            changed = sum(
                1 for pixel in difference.get_flattened_data() if pixel != (0, 0, 0, 0)
            )
            metrics.append(
                {
                    "sampleId": sample_id,
                    "intervalId": point["intervalId"],
                    "density": point["density"],
                    "fraction": point["fraction"],
                    "angleDegrees": point["angleDegrees"],
                    "meanAbsoluteDifference": stats.mean,
                    "maximumChannelDifference": max(high for _low, high in extrema),
                    "differentPixelFraction": changed / (a.width * a.height),
                    "meanEdgeDifference": ImageStat.Stat(edge_difference).mean,
                    "meanLuminanceA": sum(ImageStat.Stat(a.convert("RGB")).mean) / 3,
                    "meanLuminanceB": sum(ImageStat.Stat(b.convert("RGB")).mean) / 3,
                    "comparison": comparison_path.relative_to(output_root).as_posix(),
                    "difference": difference_path.relative_to(output_root).as_posix(),
                    "artifactInspection": {
                        "ghosting": "pending-browser-review",
                        "edgeTearing": "pending-browser-review",
                        "holeClosure": "pending-browser-review",
                        "thinRodBending": "pending-browser-review",
                        "reflectionDrift": "pending-browser-review",
                        "brightnessFlicker": "pending-browser-review",
                    },
                }
            )
    report = {
        "schema": "twinkle-stage5-png-interpolation-visual-metrics-v1",
        "samples": metrics,
        "sameTimePointCount": len(metrics),
        "formalSelectionMade": False,
    }
    _write_json(output_root / "visual-metrics.json", report)
    return report


def record_fixed_visual_verdict(repo: Path, output_root: Path) -> dict:
    """Persist the bounded visual failure observed in the fixed FFmpeg cases."""
    output_root = validate_output_root(repo, output_root)
    manifest_path = output_root / "pilot-manifest.json"
    results_path = output_root / "machine-results.json"
    metrics_path = output_root / "visual-metrics.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    observations = {
        "007-008-192-1of2": {
            "ghosting": "detected",
            "edgeTearing": "detected",
            "holeClosure": "small-hole-structure-distorted",
            "thinRodBending": "detected",
            "reflectionDrift": "detected",
        },
        "078-079-192-1of2": {
            "ghosting": "detected",
            "edgeTearing": "detected",
            "thinRodBending": "rod-edge-fragmented",
            "reflectionDrift": "detected",
        },
        "095-000-192-1of2": {
            "ghosting": "detected",
            "edgeTearing": "detected",
            "reflectionDrift": "detected",
            "seamAnomaly": "block-tearing-on-model-edges",
        },
    }
    for record in metrics["samples"]:
        if record["sampleId"] in observations:
            record["artifactInspection"].update(observations[record["sampleId"]])
    metrics["fixedVisualVerdict"] = {
        "candidate": "B",
        "status": "failed",
        "basis": sorted(observations),
        "formalSelectionMade": False,
    }
    b_result = results["candidates"]["B"]
    b_result["status"] = "failed"
    b_result["formalUsable"] = False
    b_result["recommended"] = False
    b_result["pixelContractPassed"] = True
    b_result["detectedArtifacts"] = [
        "ghosting",
        "edge-tearing",
        "small-hole-distortion",
        "thin-rod-fragmentation",
        "reflection-drift",
        "095-to-000-seam-block-tearing",
    ]
    b_result["failureEvidence"] = [
        "007->008 midpoint shows block tearing and doubled reflective/small-hole details",
        "078->079 midpoint fragments the thin rod and model edges",
        "095->000 midpoint shows seam-local block tearing and ghosted edges",
    ]
    manifest["candidates"]["B"]["status"] = "failed"
    results["machinePassed"] = results["candidates"]["A"]["status"] == "passed"
    _write_json(metrics_path, metrics)
    _write_json(manifest_path, manifest)
    _write_json(results_path, results)
    return results


def finalize_browser_results(repo: Path, output_root: Path) -> dict:
    output_root = validate_output_root(repo, output_root)
    browser = json.loads((output_root / "browser-results.json").read_text(encoding="utf-8"))
    if browser.get("machinePassed") is not True:
        raise PilotValidationError("browser results did not pass")
    results_path = output_root / "machine-results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["browserAcceptancePending"] = False
    results["browserPassed"] = True
    results["browserResultsSha256"] = sha256(output_root / "browser-results.json")
    _write_json(results_path, results)
    return results


def _blender_worker(
    mode: str, output_root: Path, points_path: Path, stage4_repo: Path
) -> int:
    import bpy
    from mathutils import Matrix, Vector

    points = json.loads(Path(points_path).read_text(encoding="utf-8"))
    output_root = Path(output_root).resolve()
    repo = Path(__file__).resolve().parents[1]
    stage4_repo = Path(stage4_repo).resolve()
    source_path = stage4_repo / "scripts/build_twinkle_stage4_orbit.py"
    stage4 = _load_module(source_path, "twinkle_stage4_render_authority")
    authority = json.loads(stage4.STAGE1_MANIFEST.read_text(encoding="utf-8"))
    profile = authority["renderProfile"]
    candidate = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate.resolve() or sha256(candidate) != EXPECTED_BLEND_SHA256:
        raise RuntimeError("wrong or drifted candidate blend")
    source_hash_before = sha256(candidate)
    scene = bpy.context.scene
    source_camera = scene.camera
    original_frame = scene.frame_current
    original_camera = scene.camera
    original_camera_matrix = source_camera.matrix_world.copy()
    original_scene = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent,
        "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {
        name: bool(bpy.data.objects[name].hide_render)
        for name in profile["sharedHiddenObjects"]
        if name in bpy.data.objects
    }
    top_plate = bpy.data.objects[profile["materialRule"]["object"]]
    material_slot = top_plate.material_slots[0]
    original_material, original_link = material_slot.material, material_slot.link
    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__STAGE5_INTERPOLATION_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE5_INTERPOLATION_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    temporary_material = None
    lights = []
    records = []
    curve_data = curve_object = target_object = camera_action = None

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_linear_fcurve(fcurves, data_path, values):
        curve = fcurves.new(data_path=data_path)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "LINEAR"
        curve.update()
        return curve
    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x, scene.render.resolution_y = (640, 450)
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = 64
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]
        chamber_target = Vector(authority["units"][stage4.CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(f"TEMP__STAGE5_INTERPOLATION_{key.upper()}_DATA", "AREA")
            data.energy, data.shape, data.size = config["energy"], "DISK", config["size"]
            obj = bpy.data.objects.new(f"TEMP__STAGE5_INTERPOLATION_{key.upper()}", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat("-Z", "Y").to_euler()
            lights.append((obj, data))
        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE5_INTERPOLATION_TOP_PLATE_NO_NORMAL"
        normal_nodes = [n for n in temporary_material.node_tree.nodes if n.bl_idname == "ShaderNodeNormalMap"]
        if len(normal_nodes) != 1:
            raise RuntimeError("normal-map authority drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"]["normalMapStrengthDuringRender"]
        material_slot.link, material_slot.material = "OBJECT", temporary_material
        camera.data.lens = stage4.ORBIT_LENS_MM
        camera.data.sensor_width = stage4.ORBIT_SENSOR_WIDTH_MM
        camera.data.shift_x, camera.data.shift_y = stage4.ORBIT_SHIFT
        pivot = Vector(stage4.ORBIT_OVERVIEW_TARGET)
        base = Vector(stage4.ORBIT_OVERVIEW_LOCATION) - pivot
        expected_locations = [
            pivot + Matrix.Rotation(math.radians(angle), 4, "Z") @ base
            for angle in stage4.c360_f96_angles()
        ]
        curve_data = bpy.data.curves.new("TEMP__STAGE5_INTERPOLATION_CURVE", type="CURVE")
        curve_data.dimensions, curve_data.path_duration = "3D", 96
        spline = curve_data.splines.new(type="POLY")
        spline.points.add(95)
        spline.use_cyclic_u = True
        for curve_point, location in zip(spline.points, expected_locations):
            curve_point.co = (*location, 1.0)
        curve_object = bpy.data.objects.new("TEMP__STAGE5_INTERPOLATION_PATH", curve_data)
        scene.collection.objects.link(curve_object)
        curve_object.matrix_world = Matrix.Identity(4)
        target_object = bpy.data.objects.new("TEMP__STAGE5_INTERPOLATION_TARGET", None)
        target_object.location = pivot
        scene.collection.objects.link(target_object)
        follow = camera.constraints.new(type="FOLLOW_PATH")
        follow.name, follow.target = "TEMP__STAGE5_INTERPOLATION_FOLLOW_PATH", curve_object
        follow.use_fixed_location, follow.use_curve_follow = True, False
        orientation = camera.constraints.new(type="TRACK_TO")
        orientation.name, orientation.target = "TEMP__STAGE5_INTERPOLATION_TRACK_TO", target_object
        orientation.track_axis, orientation.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        camera_action = bpy.data.actions.new("TEMP__STAGE5_INTERPOLATION_CAMERA_ACTION")
        camera_slot, fcurves = action_fcurves(camera_action, camera, "C360 Pilot Orbit")
        add_linear_fcurve(
            fcurves,
            f'constraints["{follow.name}"].offset_factor',
            ((1, 0.0), (97, 1.0)),
        )
        animation = camera.animation_data_create()
        animation.action, animation.action_slot = camera_action, camera_slot
        camera.location = Vector((0.0, 0.0, 0.0))
        camera.rotation_euler = (pivot - expected_locations[0]).to_track_quat("-Z", "Y").to_euler()
        camera.scale = Vector((1.0, 1.0, 1.0))

        render_points = (
            [{"id": "control-008", "angleDegrees": 30.0, "density": 96, "startFrame": 8, "fractionValue": 0.0}]
            if mode == "control"
            else points
        )
        for ordinal, point in enumerate(render_points, 1):
            angle = float(point["angleDegrees"])
            frame_value = float(point["startFrame"]) + 1.0 + float(point["fractionValue"])
            frame_number = int(math.floor(frame_value))
            scene.frame_set(frame_number, subframe=frame_value - frame_number)
            bpy.context.view_layer.update()
            location = camera.matrix_world.translation.copy()
            if mode == "control":
                target = output_root / "evidence/blender-control-frame-008.png"
            else:
                target = output_root / "candidates/A" / str(point["density"]) / f"{point['id']}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(target)
            started = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            elapsed = time.perf_counter() - started
            records.append(
                {
                    "sampleId": point["id"],
                    "src": target.relative_to(output_root).as_posix(),
                    "angleDegrees": angle,
                    "elapsedSeconds": elapsed,
                    "cameraLocation": [round(float(v), 9) for v in location],
                    "cameraRotationQuaternion": [
                        round(float(v), 9) for v in camera.matrix_world.to_quaternion()
                    ],
                    "cameraTarget": [round(float(v), 9) for v in pivot],
                }
            )
    finally:
        camera.animation_data_clear()
        if camera_action is not None and camera_action.name in bpy.data.actions:
            bpy.data.actions.remove(camera_action)
        material_slot.material, material_slot.link = original_material, original_link
        if temporary_material is not None:
            bpy.data.materials.remove(temporary_material)
        for obj, data in lights:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)
        if target_object is not None:
            bpy.data.objects.remove(target_object, do_unlink=True)
        if curve_object is not None:
            bpy.data.objects.remove(curve_object, do_unlink=True)
        if curve_data is not None and curve_data.name in bpy.data.curves:
            bpy.data.curves.remove(curve_data)
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
        scene.camera = original_camera
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.render.film_transparent = original_scene["film_transparent"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.view_settings.view_transform = original_scene["viewTransform"]
        scene.view_settings.look = original_scene["look"]
        scene.view_settings.exposure = original_scene["exposure"]
        scene.view_settings.gamma = original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()
    restored = (
        sha256(candidate) == source_hash_before
        and scene.camera == original_camera
        and all(
            abs(float(a) - float(b)) <= 1e-8
            for left, right in zip(source_camera.matrix_world, original_camera_matrix)
            for a, b in zip(left, right)
        )
    )
    _write_json(
        output_root / "work/blender-worker-results.json",
        {"mode": mode, "frames": records, "sourceRestored": restored},
    )
    if not restored:
        raise RuntimeError("Blender source restoration failed")
    return 0


def main(argv: list[str] | None = None) -> int:
    if "--" in sys.argv:
        worker_args = sys.argv[sys.argv.index("--") + 1 :]
        if "--blender-worker" in worker_args:
            parser = argparse.ArgumentParser()
            parser.add_argument("--blender-worker", choices=("control", "samples"), required=True)
            parser.add_argument("--worker-output", type=Path, required=True)
            parser.add_argument("--worker-points", type=Path, required=True)
            parser.add_argument("--worker-stage4-repo", type=Path, required=True)
            args = parser.parse_args(worker_args)
            return _blender_worker(
                args.blender_worker,
                args.worker_output,
                args.worker_points,
                args.worker_stage4_repo,
            )
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--stage4-repo", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=Path(shutil.which("ffmpeg") or "ffmpeg"))
    parser.add_argument("--refresh-a", action="store_true")
    parser.add_argument("--refresh-visual", action="store_true")
    parser.add_argument("--record-visual-verdict", action="store_true")
    parser.add_argument("--refresh-page", action="store_true")
    parser.add_argument("--finalize-browser", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output = args.output_root or repo / "output/twinkle-stage5-png-interpolation-pilot"
    if args.finalize_browser:
        report = finalize_browser_results(repo, output)
    elif args.refresh_page:
        _write_page(output)
        report = {"pageRefreshed": True}
    elif args.record_visual_verdict:
        report = record_fixed_visual_verdict(repo, output)
    elif args.refresh_visual:
        report = build_visual_evidence(repo, output)
    elif args.refresh_a:
        report = refresh_a_candidate(repo, output, args.stage4_repo, args.blender)
    else:
        report = build_pilot(repo, output, args.stage4_repo, args.blender, args.ffmpeg)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
