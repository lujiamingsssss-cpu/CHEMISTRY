"""Build the isolated complete TWINKLE A/192 real-render sequence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import build_twinkle_stage5_png_interpolation_pilot as interpolation


CANDIDATE_ID = "A"
AUTHORITY_FRAME_COUNT = 96
MIDPOINT_FRAME_COUNT = 96
TOTAL_FRAME_COUNT = 192
ORBIT_DURATION_MS = 8_000
FIXED_FPS = 24
ANGLE_STEP_DEGREES = 1.875
CONTROL_MAX_CHANNEL_DELTA = 1
CONTROL_MAX_DIFFERENT_PIXEL_FRACTION = 0.0002
EXPECTED_BLEND_SHA256 = interpolation.EXPECTED_BLEND_SHA256
RENDER_SETTINGS = {"resolution": [640, 450], "samples": 64, "format": "PNG", "mode": "RGBA"}


class FullSequenceValidationError(ValueError):
    """Raised when the isolated full-sequence contract is violated."""


sha256 = interpolation.sha256


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_output_root(repo: Path, output_root: Path) -> Path:
    expected = (Path(repo).resolve() / "output/twinkle-stage5-a192-full-sequence").resolve()
    actual = Path(output_root).resolve()
    if actual != expected:
        raise FullSequenceValidationError(f"A/192 output must be exactly {expected}")
    return actual


def registered_stage4_worktree(repo: Path) -> Path:
    return interpolation.registered_worktree_for_branch(repo, interpolation.STAGE4_BRANCH)


def stage4_sources(repo: Path, stage4_repo: Path) -> dict:
    return interpolation.stage4_source_paths(repo, stage4_repo)


def load_authority(repo: Path) -> dict:
    return interpolation.load_authority(repo)


def midpoint_points(authority: dict) -> list[dict]:
    points = []
    for index in range(AUTHORITY_FRAME_COUNT):
        end = (index + 1) % AUTHORITY_FRAME_COUNT
        start_angle = authority["frames"][index]["angleDegrees"]
        end_angle = authority["frames"][end]["angleDegrees"]
        delta = (end_angle - start_angle) % 360.0
        points.append(
            {
                "id": f"{index:03d}-{end:03d}-192-1of2",
                "startFrame": index,
                "endFrame": end,
                "density": TOTAL_FRAME_COUNT,
                "fraction": "1/2",
                "fractionValue": 0.5,
                "angleDegrees": (start_angle + delta * 0.5) % 360.0,
                "sequenceIndex": index * 2 + 1,
            }
        )
    return points


def _tree_snapshot(root: Path) -> dict:
    root = Path(root).resolve()
    records = []
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "path": str(root),
        "fileCount": len(records),
        "bytes": sum(record["bytes"] for record in records),
        "treeSha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def _authority_snapshot(authority: dict) -> dict:
    records = []
    for index, record in authority["frames"].items():
        path = record["path"]
        actual = {"index": index, "sha256": sha256(path), "bytes": path.stat().st_size}
        if actual["sha256"] != record["sha256"] or actual["bytes"] != record["bytes"]:
            raise FullSequenceValidationError(f"authority frame drift: {index:03d}")
        records.append(actual)
    return {"frameCount": len(records), "inventory": records}


def _protected_snapshot(repo: Path, authority: dict, sources: dict) -> dict:
    repo = Path(repo)
    return {
        "authority": _authority_snapshot(authority),
        "stage4": interpolation._source_snapshot(sources),
        "formal": interpolation._formal_snapshot(repo),
        "priorPilots": {
            "interpolation": _tree_snapshot(repo / "output/twinkle-stage5-png-interpolation-pilot"),
            "interpolationBrowser": _tree_snapshot(repo / "output/playwright/twinkle-stage5-png-interpolation-pilot"),
            "fixedOrbit": _tree_snapshot(repo / "output/twinkle-stage5-fixed-orbit-drag-pilot"),
            "fixedOrbitBrowser": _tree_snapshot(repo / "output/playwright/twinkle-stage5-fixed-orbit-drag-pilot"),
        },
        "protectedFiles": {
            name: {"sha256": sha256(repo / relative), "bytes": (repo / relative).stat().st_size}
            for name, relative in {
                "fixedBuilder": "scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py",
                "fixedTest": "tests/test_twinkle_stage5_fixed_orbit_drag_pilot.py",
                "interpolationBuilder": "scripts/build_twinkle_stage5_png_interpolation_pilot.py",
                "interpolationTest": "tests/test_twinkle_stage5_png_interpolation_pilot.py",
            }.items()
        },
    }


def _copy_authorities(output_root: Path, authority: dict) -> list[dict]:
    frames_root = output_root / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    records = []
    for source_index in range(AUTHORITY_FRAME_COUNT):
        sequence_index = source_index * 2
        source = authority["frames"][source_index]
        target = frames_root / f"frame-{sequence_index:03d}.png"
        shutil.copyfile(source["path"], target)
        if sha256(target) != source["sha256"] or target.stat().st_size != source["bytes"]:
            raise FullSequenceValidationError(f"authority copy drift: {source_index:03d}")
        records.append(
            {
                "index": sequence_index,
                "sequenceIndex": sequence_index,
                "sourceAuthorityIndex": source_index,
                "kind": "authority",
                "angleDegrees": source_index * 3.75,
                "src": target.relative_to(output_root).as_posix(),
                "sha256": source["sha256"],
                "bytes": source["bytes"],
                "sourceFrames": [source_index],
                "hotspots": source["hotspots"],
            }
        )
    return records


def _run_render(
    output_root: Path,
    sources: dict,
    blender: Path,
    points: list[dict],
    authority: dict,
) -> tuple[dict, list[dict]]:
    points_path = output_root / "work/midpoint-points.json"
    _write_json(points_path, points)
    worker_script = Path(interpolation.__file__).resolve()
    control_run = interpolation._run(
        interpolation.blender_command(
            blender,
            sources["candidateBlend"],
            worker_script,
            output_root,
            sources["repo"],
            "control",
            points_path,
        )
    )
    _write_json(output_root / "evidence/blender-control-command.json", control_run)
    if control_run["exitCode"] != 0:
        raise FullSequenceValidationError("authority control render command failed")
    control_audit = json.loads(
        (output_root / "work/blender-worker-results.json").read_text(encoding="utf-8")
    )["frames"][0]
    stage4_manifest = json.loads(sources["manifest"].read_text(encoding="utf-8"))
    expected_camera = stage4_manifest["frames"][8]["camera"]
    control_path = output_root / "evidence/blender-control-frame-008.png"
    authority_path = authority["frames"][8]["path"]
    comparison = interpolation._pixel_comparison(control_path, authority_path)
    contract = interpolation._pixel_contract(control_path)
    expected_contract = interpolation._pixel_contract(authority_path)
    camera_exact = (
        control_audit["cameraLocation"] == expected_camera["location"]
        and control_audit["cameraRotationQuaternion"] == expected_camera["rotationQuaternion"]
    )
    control_passed = (
        camera_exact
        and contract == expected_contract
        and comparison["maximumChannelDelta"] <= CONTROL_MAX_CHANNEL_DELTA
        and comparison["differentPixelFraction"] <= CONTROL_MAX_DIFFERENT_PIXEL_FRACTION
    )
    control = {
        "passed": control_passed,
        "cameraExact": camera_exact,
        "pixelContract": contract,
        "authorityPixelContract": expected_contract,
        "pixelComparison": comparison,
        "elapsedSeconds": control_run["elapsedSeconds"],
    }
    _write_json(output_root / "evidence/control-results.json", control)
    if not control_passed:
        raise FullSequenceValidationError("authority control gate failed")

    sample_run = interpolation._run(
        interpolation.blender_command(
            blender,
            sources["candidateBlend"],
            worker_script,
            output_root,
            sources["repo"],
            "samples",
            points_path,
        )
    )
    _write_json(output_root / "evidence/blender-midpoint-command.json", sample_run)
    if sample_run["exitCode"] != 0:
        raise FullSequenceValidationError("midpoint render command failed")
    audit = json.loads(
        (output_root / "work/blender-worker-results.json").read_text(encoding="utf-8")
    )
    if audit.get("sourceRestored") is not True or len(audit.get("frames", [])) != 96:
        raise FullSequenceValidationError("midpoint render count or restoration failed")
    by_id = {point["id"]: point for point in points}
    records = []
    for rendered in audit["frames"]:
        point = by_id[rendered["sampleId"]]
        source_path = output_root / rendered["src"]
        target = output_root / "frames" / f"frame-{point['sequenceIndex']:03d}.png"
        source_path.replace(target)
        pixel_contract = interpolation._pixel_contract(target)
        if pixel_contract != {
            "format": "PNG",
            "mode": "RGBA",
            "size": [640, 450],
            "alphaExtrema": [255, 255],
            "srgb": True,
            "gamma": 0.45455,
        }:
            raise FullSequenceValidationError(f"midpoint pixel contract failed: {point['id']}")
        records.append(
            {
                "index": point["sequenceIndex"],
                "sequenceIndex": point["sequenceIndex"],
                "sourceAuthorityIndex": point["startFrame"],
                "kind": "real-midpoint",
                "angleDegrees": point["angleDegrees"],
                "src": target.relative_to(output_root).as_posix(),
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
                "elapsedSeconds": rendered["elapsedSeconds"],
                "sourceFrames": [point["startFrame"], point["endFrame"]],
                "cameraLocation": rendered["cameraLocation"],
                "cameraRotationQuaternion": rendered["cameraRotationQuaternion"],
                "cameraTarget": rendered["cameraTarget"],
                "renderSettings": dict(RENDER_SETTINGS),
                "hotspots": authority["frames"][point["startFrame"]]["hotspots"],
            }
        )
    return {
        "control": control,
        "midpointCommandElapsedSeconds": sample_run["elapsedSeconds"],
        "midpointRenderElapsedSeconds": sum(record["elapsedSeconds"] for record in records),
    }, records


_fixed = interpolation.load_fixed_pilot_module(Path(__file__).resolve().parents[1])
PLAYER_CSS = _fixed.PILOT_CSS + r'''
.orbit-viewport{background:rgb(233 234 233)}
html[data-embedded="true"],html[data-embedded="true"] body{overflow:hidden}
html[data-embedded="true"] .pilot-status,html[data-embedded="true"] .selection-status,html[data-embedded="true"] .audit-spacer{display:none}
html[data-embedded="true"] .orbit-viewport{height:100vh;min-height:0}
'''


PLAYER_HTML = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>TWINKLE A/192 完整候选</title><link rel="stylesheet" href="player.css"></head>
<body><main id="orbit-viewport" class="orbit-viewport" data-testid="orbit-viewport" data-held="false"><img id="orbit-frame" class="orbit-frame" alt="TWINKLE A/192 完整 360° 候选"><p id="pilot-status" class="pilot-status" aria-live="polite">正在解码首帧</p><p id="selection-status" class="selection-status" aria-live="polite">A/192 隔离审核；不进入正式主页</p><button class="hotspot chamber" type="button" data-unit="dual_channel_collection_optics_chamber" aria-label="双通道采集光学舱" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">双通道采集光学舱</span></button><button class="hotspot condenser" type="button" data-unit="dual_channel_condenser_lens_assembly" aria-label="聚光镜组件" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">聚光镜组件</span></button></main><div class="audit-spacer" aria-hidden="true"></div><script src="player.js"></script></body></html>
'''


PLAYER_JS = r'''
'use strict';
const TOTAL_FRAME_COUNT=192;
const ORBIT_DURATION_MS=8000;
const FIXED_FPS=24;
const CLICK_DRAG_THRESHOLD_PX=6;
const HOTSPOT_SPEED_FACTOR=.67;
const HOTSPOT_LEAVE_GRACE_MS=100;
const HOTSPOT_ENTER_TRANSITION_MS=120;
const SPEED_RECOVERY_MS=180;
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
const embedded=new URLSearchParams(location.search).get('embedded')==='1';
if(embedded)document.documentElement.dataset.embedded='true';
const viewport=document.querySelector('#orbit-viewport'),frameImage=document.querySelector('#orbit-frame'),statusLine=document.querySelector('#pilot-status'),selectionLine=document.querySelector('#selection-status');
const hotspotElements=new Map([...document.querySelectorAll('[data-unit]')].map(element=>[element.dataset.unit,element]));
const decodedFrames=new Map(),eventLog=[],fadeTimers=new Map();
const state={manifest:null,orbitPositionFrames:0,displayedFrame:-1,lastTimestamp:null,ready:false,firstFrameDisplayed:false,resourceError:false,reducedMotion:reducedMotion.matches,viewportVisible:true,documentVisible:document.visibilityState==='visible',windowFocused:true,destroyed:false,overviewActive:true,safePaused:true,safeReasons:['resources-not-ready'],currentSpeedFactor:0,targetSpeedFactor:0,speedTransition:null,pointer:{activeId:null,held:false,dragging:false,startX:0,startY:0,startPositionFrames:0,viewportWidth:1,suppressNextClick:false,pressHotspotUnit:null},hotspotIntent:{hovered:new Set(),focused:new Set(),leaveTimers:new Map()},frameHistory:[],completedCycles:0};
function log(type,detail={}){eventLog.push({type,time:performance.now(),...detail});if(eventLog.length>800)eventLog.shift();}
function wrapFrames(value){return((value%TOTAL_FRAME_COUNT)+TOTAL_FRAME_COUNT)%TOTAL_FRAME_COUNT;}
function frameIndex(){return Math.floor(wrapFrames(state.orbitPositionFrames))%TOTAL_FRAME_COUNT;}
function computeSafeReasons(){const reasons=[];if(!state.ready)reasons.push('resources-not-ready');if(state.resourceError)reasons.push('resource-error');if(state.reducedMotion)reasons.push('reduced-motion');if(!state.viewportVisible)reasons.push('viewport-hidden');if(!state.documentVisible)reasons.push('document-hidden');if(!state.windowFocused)reasons.push('window-blurred');if(!state.overviewActive)reasons.push('non-overview');if(state.destroyed)reasons.push('destroyed');return reasons;}
function desiredSpeedFactor(){state.safeReasons=computeSafeReasons();state.safePaused=state.safeReasons.length>0;if(state.safePaused)return 0;if(state.pointer.held)return 0;if(state.hotspotIntent.hovered.size||state.hotspotIntent.focused.size)return HOTSPOT_SPEED_FACTOR;return 1;}
function refreshSpeedIntent(now=performance.now()){updateSpeed(now);const desired=desiredSpeedFactor();if(desired===state.targetSpeedFactor)return;state.targetSpeedFactor=desired;if(state.safePaused||state.pointer.held){state.currentSpeedFactor=desired;state.speedTransition=null;}else state.speedTransition={from:state.currentSpeedFactor,to:desired,started:now,duration:desired===HOTSPOT_SPEED_FACTOR?HOTSPOT_ENTER_TRANSITION_MS:SPEED_RECOVERY_MS};log('speed-intent',{desired});}
function updateSpeed(now){if(!state.speedTransition)return;const transition=state.speedTransition,progress=Math.min(1,Math.max(0,(now-transition.started)/transition.duration)),eased=1-(1-progress)*(1-progress);state.currentSpeedFactor=transition.from+(transition.to-transition.from)*eased;if(progress>=1){state.currentSpeedFactor=transition.to;state.speedTransition=null;}}
function clearHotspotIntent(unit){state.hotspotIntent.hovered.delete(unit);state.hotspotIntent.focused.delete(unit);const timer=state.hotspotIntent.leaveTimers.get(unit);if(timer)clearTimeout(timer);state.hotspotIntent.leaveTimers.delete(unit);refreshSpeedIntent();}
function imageContentBox(){const imageRect=frameImage.getBoundingClientRect(),viewportRect=viewport.getBoundingClientRect(),imageAspect=frameImage.naturalWidth/frameImage.naturalHeight,boxAspect=imageRect.width/imageRect.height,width=boxAspect>imageAspect?imageRect.height*imageAspect:imageRect.width,height=boxAspect>imageAspect?imageRect.height:imageRect.width/imageAspect;return{offsetX:imageRect.left-viewportRect.left+(imageRect.width-width)/2,offsetY:imageRect.top-viewportRect.top+(imageRect.height-height)/2,width,height};}
function positionHotspotInImageContent(element,projection){const content=imageContentBox(),x=content.offsetX+projection[0]*content.width,y=content.offsetY+projection[1]*content.height;element.style.left=x+'px';element.style.top=y+'px';}
function scheduleHotspotVisibility(element,record){const unit=element.dataset.unit,isVisible=record.status==='visible'&&record.eligible===true;clearTimeout(fadeTimers.get(element));positionHotspotInImageContent(element,record.projection);if(isVisible){element.hidden=false;element.disabled=false;element.style.pointerEvents='auto';element.setAttribute('aria-hidden','false');requestAnimationFrame(()=>element.classList.add('is-visible'));return;}clearHotspotIntent(unit);element.disabled=true;element.style.pointerEvents='none';element.setAttribute('aria-hidden','true');element.classList.remove('is-visible');if(document.activeElement===element)element.blur();const timer=setTimeout(()=>{if(element.getAttribute('aria-hidden')==='true')element.hidden=true;},140);fadeTimers.set(element,timer);}
function renderFrame(force=false){if(!state.manifest)return;const index=frameIndex();if(!force&&index===state.displayedFrame)return;const decoded=decodedFrames.get(index);if(!decoded)return;const record=state.manifest.frames[index];frameImage.src=decoded.src;state.displayedFrame=index;for(const[unit,hotspot]of Object.entries(record.hotspots))scheduleHotspotVisibility(hotspotElements.get(unit),hotspot);state.frameHistory.push({index,time:performance.now(),positionFrames:state.orbitPositionFrames});if(state.frameHistory.length>1200)state.frameHistory.shift();document.body.dataset.frame=String(index);document.body.dataset.angle=String(record.angleDegrees);}
function animationLoop(now){if(state.lastTimestamp===null)state.lastTimestamp=now;const elapsedMs=Math.min(100,Math.max(0,now-state.lastTimestamp));state.lastTimestamp=now;refreshSpeedIntent(now);updateSpeed(now);if(state.currentSpeedFactor>0){const before=state.orbitPositionFrames;state.orbitPositionFrames=wrapFrames(state.orbitPositionFrames+elapsedMs*TOTAL_FRAME_COUNT/ORBIT_DURATION_MS*state.currentSpeedFactor);if(state.orbitPositionFrames<before)state.completedCycles+=1;renderFrame();}else renderFrame();statusLine.textContent=`frame-${String(frameIndex()).padStart(3,'0')} · 24 fps · ${Math.round(state.currentSpeedFactor*100)}%`;viewport.dataset.held=String(state.pointer.held);requestAnimationFrame(animationLoop);}
function pointerEligible(event){return event.button===0&&event.isPrimary!==false;}
function onPointerDown(event){if(!pointerEligible(event)||state.pointer.activeId!==null)return;state.pointer.activeId=event.pointerId;state.pointer.held=true;state.pointer.dragging=false;state.pointer.startX=event.clientX;state.pointer.startY=event.clientY;state.pointer.startPositionFrames=state.orbitPositionFrames;state.pointer.viewportWidth=Math.max(1,viewport.getBoundingClientRect().width);state.pointer.pressHotspotUnit=event.target.closest?.('.hotspot')?.dataset.unit||null;viewport.setPointerCapture(event.pointerId);refreshSpeedIntent();log('pointer-captured',{pointerId:event.pointerId,pointerType:event.pointerType});}
function onPointerMove(event){if(event.pointerId!==state.pointer.activeId||!state.pointer.held)return;const dx=event.clientX-state.pointer.startX,dy=event.clientY-state.pointer.startY;if(!state.pointer.dragging&&Math.hypot(dx,dy)>CLICK_DRAG_THRESHOLD_PX){state.pointer.dragging=true;log('drag-start',{dx,dy});}if(!state.pointer.dragging)return;event.preventDefault();state.orbitPositionFrames=wrapFrames(state.pointer.startPositionFrames-dx/state.pointer.viewportWidth*TOTAL_FRAME_COUNT);renderFrame(true);}
function finishPointer(event,reason){if(event.pointerId!==state.pointer.activeId)return;const pointerId=state.pointer.activeId,wasDragging=state.pointer.dragging,pressHotspotUnit=state.pointer.pressHotspotUnit;state.pointer.activeId=null;state.pointer.held=false;state.pointer.dragging=false;state.pointer.pressHotspotUnit=null;if(viewport.hasPointerCapture(pointerId)&&reason!=='lostpointercapture')viewport.releasePointerCapture(pointerId);if(!wasDragging&&pressHotspotUnit&&reason==='pointerup')hotspotElements.get(pressHotspotUnit).click();refreshSpeedIntent();log('pointer-release',{reason});}
viewport.addEventListener('pointerdown',onPointerDown);viewport.addEventListener('pointermove',onPointerMove,{passive:false});viewport.addEventListener('pointerup',event=>finishPointer(event,'pointerup'));viewport.addEventListener('pointercancel',event=>finishPointer(event,'pointercancel'));viewport.addEventListener('lostpointercapture',event=>finishPointer(event,'lostpointercapture'));
for(const[unit,element]of hotspotElements){element.addEventListener('pointerenter',()=>{const timer=state.hotspotIntent.leaveTimers.get(unit);if(timer)clearTimeout(timer);state.hotspotIntent.leaveTimers.delete(unit);state.hotspotIntent.hovered.add(unit);refreshSpeedIntent();});element.addEventListener('pointerleave',()=>{const prior=state.hotspotIntent.leaveTimers.get(unit);if(prior)clearTimeout(prior);const timer=setTimeout(()=>{state.hotspotIntent.leaveTimers.delete(unit);state.hotspotIntent.hovered.delete(unit);refreshSpeedIntent();},HOTSPOT_LEAVE_GRACE_MS);state.hotspotIntent.leaveTimers.set(unit,timer);});element.addEventListener('focus',()=>{state.hotspotIntent.focused.add(unit);refreshSpeedIntent();});element.addEventListener('blur',()=>{state.hotspotIntent.focused.delete(unit);refreshSpeedIntent();});}
const observer=new IntersectionObserver(entries=>{state.viewportVisible=entries.some(entry=>entry.isIntersecting);refreshSpeedIntent();},{threshold:.05});observer.observe(viewport);document.addEventListener('visibilitychange',()=>{state.documentVisible=document.visibilityState==='visible';state.lastTimestamp=null;refreshSpeedIntent();});addEventListener('blur',()=>{state.windowFocused=false;refreshSpeedIntent();});addEventListener('focus',()=>{state.windowFocused=true;state.lastTimestamp=null;refreshSpeedIntent();});
addEventListener('resize',()=>renderFrame(true));
reducedMotion.addEventListener('change',event=>{state.reducedMotion=event.matches;if(event.matches)state.orbitPositionFrames=0;state.lastTimestamp=null;refreshSpeedIntent();renderFrame(true);});
async function decodeFrame(record){const image=new Image();image.src=record.src;await image.decode();decodedFrames.set(record.index,image);return image;}
async function setPositionAndWait(value){const target=Math.floor(wrapFrames(value))%TOTAL_FRAME_COUNT;if(!decodedFrames.has(target))throw Error('target frame unavailable');state.orbitPositionFrames=wrapFrames(value);renderFrame(true);if(state.displayedFrame!==target)throw Error('target frame unavailable');await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));if(state.displayedFrame!==target)throw Error('target frame paint drift');const paintedAt=performance.now();log('frame-painted',{target,paintedAt});return{target,displayedFrame:state.displayedFrame,paintedAt};}
fetch('a192-manifest.json').then(response=>{if(!response.ok)throw new Error('manifest '+response.status);return response.json();}).then(async manifest=>{if(manifest.frameCount!==TOTAL_FRAME_COUNT||manifest.durationMs!==ORBIT_DURATION_MS||manifest.fps!==FIXED_FPS||manifest.direction!=='forward'||manifest.cacheStrategy!=='fixed-complete-192')throw new Error('manifest contract drift');state.manifest=manifest;await decodeFrame(manifest.frames[0]);state.firstFrameDisplayed=true;renderFrame(true);statusLine.textContent='首帧已显示 · 正在解码固定缓存';await Promise.all(manifest.frames.slice(1).map(decodeFrame));if(decodedFrames.size!==TOTAL_FRAME_COUNT)throw new Error('decoded cache count drift');state.ready=true;refreshSpeedIntent();log('resources-ready',{frameCount:decodedFrames.size});}).catch(error=>{state.resourceError=true;refreshSpeedIntent();statusLine.textContent='资源失败，已安全暂停';console.error(error);});
window.__twinkleA192={snapshot:()=>({frameIndex:frameIndex(),orbitPositionFrames:state.orbitPositionFrames,displayedFrame:state.displayedFrame,currentSpeedFactor:state.currentSpeedFactor,targetSpeedFactor:state.targetSpeedFactor,held:state.pointer.held,dragging:state.pointer.dragging,ready:state.ready,firstFrameDisplayed:state.firstFrameDisplayed,decodedFrameCount:decodedFrames.size,cacheStrategy:'fixed-complete-192',completedCycles:state.completedCycles,reducedMotion:state.reducedMotion,mode:state.reducedMotion?'static-authoritative':'motion',displayedSource:state.manifest?.frames[state.displayedFrame]?.src||null,displayedHotspots:state.manifest?.frames[state.displayedFrame]?.hotspots||null,errors:state.resourceError?['resource-error']:[]}),events:()=>eventLog.map(x=>({...x})),frameHistory:()=>state.frameHistory.map(x=>({...x})),contentRect:()=>imageContentBox(),setPosition:value=>{state.orbitPositionFrames=wrapFrames(value);renderFrame(true);},setPositionAndWait};
requestAnimationFrame(animationLoop);
'''.strip()


def _write_player(output_root: Path) -> None:
    (output_root / "index.html").write_text(PLAYER_HTML, encoding="utf-8")
    (output_root / "player.css").write_text(PLAYER_CSS + "\n", encoding="utf-8")
    (output_root / "player.js").write_text(PLAYER_JS + "\n", encoding="utf-8")


def build_full_sequence(repo: Path, output_root: Path, blender: Path) -> dict:
    repo = Path(repo).resolve()
    output_root = validate_output_root(repo, output_root)
    if (output_root / "a192-manifest.json").exists():
        raise FileExistsError(f"refusing to overwrite complete A/192 output: {output_root}")
    if not (output_root / "evidence/red-evidence.json").is_file():
        raise FullSequenceValidationError("correct RED evidence is required")
    stage4_repo = registered_stage4_worktree(repo)
    sources = stage4_sources(repo, stage4_repo)
    authority = load_authority(repo)
    before = _protected_snapshot(repo, authority, sources)
    authority_records = _copy_authorities(output_root, authority)
    points = midpoint_points(authority)
    render_result, midpoint_records = _run_render(
        output_root, sources, Path(blender).resolve(), points, authority
    )
    frames = sorted(authority_records + midpoint_records, key=lambda record: record["sequenceIndex"])
    if len(frames) != TOTAL_FRAME_COUNT or [record["sequenceIndex"] for record in frames] != list(range(TOTAL_FRAME_COUNT)):
        raise FullSequenceValidationError("assembled sequence is not exactly 192 ordered frames")
    manifest = {
        "schema": "twinkle-stage5-a192-full-sequence-v1",
        "candidate": CANDIDATE_ID,
        "frameCount": TOTAL_FRAME_COUNT,
        "authorityFrameCount": AUTHORITY_FRAME_COUNT,
        "renderedMidpointCount": MIDPOINT_FRAME_COUNT,
        "fps": FIXED_FPS,
        "durationMs": ORBIT_DURATION_MS,
        "angleStepDegrees": ANGLE_STEP_DEGREES,
        "direction": "forward",
        "seam": "191->000",
        "cacheStrategy": "fixed-complete-192",
        "frames": frames,
        "hotspotRule": "midpoint-holds-previous-authority-without-projection-interpolation",
        "homepageHotspotMappingAuthorized": False,
        "formalIntegrationAuthorized": False,
    }
    _write_json(output_root / "a192-manifest.json", manifest)
    _write_player(output_root)
    after = _protected_snapshot(repo, authority, sources)
    results = {
        "schema": "twinkle-stage5-a192-full-sequence-machine-results-v1",
        "machinePassed": before == after,
        "candidate": CANDIDATE_ID,
        "authorityFrameCount": AUTHORITY_FRAME_COUNT,
        "renderedMidpointCount": len(midpoint_records),
        "totalFrameCount": len(frames),
        "orbitDurationMs": ORBIT_DURATION_MS,
        "fixedFps": FIXED_FPS,
        "seam": "191->000",
        "render": render_result,
        "authorityProtection": {"before": before["authority"], "after": after["authority"], "unchanged": before["authority"] == after["authority"]},
        "stage4Protection": {"before": before["stage4"], "after": after["stage4"], "unchanged": before["stage4"] == after["stage4"]},
        "formalProtection": {"before": before["formal"], "after": after["formal"], "unchanged": before["formal"] == after["formal"], "formalFileCount": before["formal"]["fileCount"]},
        "priorPilotProtection": {"before": {"trees": before["priorPilots"], "files": before["protectedFiles"]}, "after": {"trees": after["priorPilots"], "files": after["protectedFiles"]}, "unchanged": before["priorPilots"] == after["priorPilots"] and before["protectedFiles"] == after["protectedFiles"]},
        "formalWrites": 0,
        "formalIntegrationAuthorized": False,
        "registryModificationAuthorized": False,
        "homepageModificationAuthorized": False,
        "mobileLabelModificationAuthorized": False,
        "browserAcceptancePending": True,
    }
    if results["machinePassed"] is not True:
        raise FullSequenceValidationError("protected baseline changed during build")
    _write_json(output_root / "machine-results.json", results)
    return results


def repair_player_frame_indices(repo: Path, output_root: Path) -> dict:
    output_root = validate_output_root(repo, output_root)
    manifest_path = output_root / "a192-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest.get("frames", [])) != TOTAL_FRAME_COUNT:
        raise FullSequenceValidationError("player repair requires the complete 192-frame manifest")
    for sequence_index, record in enumerate(manifest["frames"]):
        if record.get("sequenceIndex") != sequence_index:
            raise FullSequenceValidationError("sequence index drift during player repair")
        record["index"] = sequence_index
    _write_json(manifest_path, manifest)
    _write_player(output_root)
    return {"frameIndicesRepaired": TOTAL_FRAME_COUNT, "decodedCacheGate": TOTAL_FRAME_COUNT}


def finalize_browser_results(repo: Path, output_root: Path) -> dict:
    output_root = validate_output_root(repo, output_root)
    browser_path = output_root / "browser-results.json"
    browser = json.loads(browser_path.read_text(encoding="utf-8"))
    if browser.get("machinePassed") is not True:
        raise FullSequenceValidationError("browser acceptance did not pass")
    results_path = output_root / "machine-results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["browserAcceptancePending"] = False
    results["browserPassed"] = True
    results["browserResultsSha256"] = sha256(browser_path)
    _write_json(results_path, results)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--repair-player-frame-indices", action="store_true")
    parser.add_argument("--finalize-browser", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output = args.output_root or repo / "output/twinkle-stage5-a192-full-sequence"
    if args.finalize_browser:
        result = finalize_browser_results(repo, output)
    elif args.repair_player_frame_indices:
        result = repair_player_frame_indices(repo, output)
    else:
        result = build_full_sequence(repo, output, args.blender)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
