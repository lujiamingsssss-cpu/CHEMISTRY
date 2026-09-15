"""Build the isolated TWINKLE fixed-orbit drag interaction pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


FRAME_COUNT = 96
ORBIT_DURATION_MS = 8_000
ANGLE_STEP_DEGREES = 3.75
PLAYBACK_DIRECTION = "forward"
CLICK_DRAG_THRESHOLD_PX = 6
HOTSPOT_SPEED_FACTOR = 0.30
HOTSPOT_LEAVE_GRACE_MS = 100
SPEED_RECOVERY_MS = 180
APPROVED_REGISTRY_SHA256 = (
    "8D32267C20218FA575E34E78415D69EEFA58F76C4CF71CBB7903952E7EFB03C4"
)
APPROVED_C360_MANIFEST_SHA256 = (
    "8D774A5821AF2D66AFF6480465C2F69007A556B0FAAA9B831FD9E3ADF51E3623"
)
HOTSPOT_UNITS = (
    "dual_channel_collection_optics_chamber",
    "dual_channel_condenser_lens_assembly",
)
HOTSPOT_NAMES = {
    HOTSPOT_UNITS[0]: "双通道采集光学舱",
    HOTSPOT_UNITS[1]: "聚光镜组件",
}
EXPECTED_ORBIT_PROFILE = {
    "id": "C360-F96",
    "topology": "cyclic",
    "azimuthDegrees": [0.0, 360.0],
    "endExclusive": True,
    "elevationMode": "fixed",
    "durationMs": ORBIT_DURATION_MS,
    "physicalFrameCount": FRAME_COUNT,
    "logicalIndexCount": FRAME_COUNT,
    "angleStepDegrees": ANGLE_STEP_DEGREES,
    "maximumTurnDurationMs": 2_000,
    "maximumAngularSpeedDegreesPerSecond": 90.0,
    "accelerationRampMs": 250,
    "decelerationRampMs": 250,
    "settledHoldMs": 100,
    "maximumEntryFramesPerUnit": 2,
}


class PilotValidationError(ValueError):
    """Raised when an authority or isolated output violates the pilot boundary."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _write_json(path: Path, value: dict) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def validate_output_root(repo: Path, output_root: Path) -> Path:
    repo = Path(repo).resolve()
    output_root = Path(output_root).resolve()
    expected = (repo / "output" / "twinkle-stage5-fixed-orbit-drag-pilot").resolve()
    if output_root != expected:
        raise PilotValidationError(f"fixed-orbit pilot output must be exactly {expected}")
    return output_root


def validate_approved_registry(path: Path) -> str:
    actual = sha256(path)
    if actual != APPROVED_REGISTRY_SHA256:
        raise PilotValidationError("stage-5 authority does not match approved registry SHA")
    return actual


def validate_approved_c360_manifest(path: Path) -> str:
    actual = sha256(path)
    if actual != APPROVED_C360_MANIFEST_SHA256:
        raise PilotValidationError("authority does not match approved C360 manifest SHA")
    return actual


def load_authority(repo: Path) -> dict:
    repo = Path(repo).resolve()
    registry_path = repo / "registry" / "twinkle" / "stage5-runtime-assets.json"
    registry_sha = validate_approved_registry(registry_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    authority_records = {record["id"]: record for record in registry["authorities"]}
    c360_authority = authority_records.get("stage4-c360")
    if not c360_authority:
        raise PilotValidationError("stage4-c360 authority is missing")
    c360_path = repo / c360_authority["copyPath"]
    c360_sha = validate_approved_c360_manifest(c360_path)
    if (
        c360_authority.get("sha256") != c360_sha
        or c360_authority.get("bytes") != c360_path.stat().st_size
    ):
        raise PilotValidationError("registry C360 authority record has drifted")
    c360 = json.loads(c360_path.read_text(encoding="utf-8"))
    if c360.get("schema") != "twinkle-stage4-orbit-c360-f96-v1":
        raise PilotValidationError("C360 authority schema has drifted")
    if c360.get("orbitProfile") != EXPECTED_ORBIT_PROFILE:
        raise PilotValidationError("approved C360 orbit profile has drifted")
    if (
        c360.get("humanVisualApproved") is not True
        or c360.get("machinePassed") is not True
        or c360.get("physicalFrameCount") != FRAME_COUNT
        or c360.get("logicalIndexCount") != FRAME_COUNT
        or c360.get("focusRouteGenerated") is not False
    ):
        raise PilotValidationError("C360 approval or scope boundary has drifted")

    inventory = {
        record["targetPath"]: record
        for record in registry["runtimeInventory"]["files"]
        if record.get("role") == "c360"
    }
    if len(inventory) != FRAME_COUNT:
        raise PilotValidationError("registry must contain exactly 96 C360 frames")
    manifest_frames = sorted(
        c360.get("frames", []), key=lambda record: record["physicalFrameIndex"]
    )
    if [record.get("physicalFrameIndex") for record in manifest_frames] != list(
        range(FRAME_COUNT)
    ):
        raise PilotValidationError("C360 physical frame indices are not 000 through 095")

    frames = {}
    for index, source in enumerate(manifest_frames):
        target = f"showcase/homepage/assets/twinkle/c360/frame-{index:03d}.png"
        inventory_record = inventory.get(target)
        if not inventory_record:
            raise PilotValidationError(f"registry C360 frame missing: {index:03d}")
        path = repo / target
        if (
            source.get("sha256") != inventory_record.get("sha256")
            or not path.is_file()
            or sha256(path) != inventory_record.get("sha256")
            or path.stat().st_size != inventory_record.get("bytes")
        ):
            raise PilotValidationError(f"formal C360 frame drift: {index:03d}")
        qualification = source.get("qualificationByUnit", {})
        if set(qualification) != set(HOTSPOT_UNITS):
            raise PilotValidationError(f"C360 hotspot authority missing: {index:03d}")
        hotspots = {}
        for unit in HOTSPOT_UNITS:
            hotspot = qualification[unit]
            status = hotspot.get("status")
            projection = hotspot.get("projection")
            if status not in {"visible", "back-facing", "occluded", "out-of-safe"}:
                raise PilotValidationError("C360 hotspot status is invalid")
            if (
                not isinstance(projection, list)
                or len(projection) != 2
                or any(not isinstance(value, (int, float)) for value in projection)
            ):
                raise PilotValidationError("C360 hotspot projection is invalid")
            hotspots[unit] = {
                "status": status,
                "projection": [float(projection[0]), float(projection[1])],
                "eligible": status == "visible",
            }
        frames[index] = {
            "path": path,
            "sha256": inventory_record["sha256"],
            "bytes": inventory_record["bytes"],
            "angleDegrees": float(source["azimuthDegrees"]),
            "hotspots": hotspots,
        }
    return {
        "repo": repo,
        "registrySha256": registry_sha,
        "c360ManifestSha256": c360_sha,
        "orbitProfile": dict(c360["orbitProfile"]),
        "frames": frames,
    }


PILOT_CSS = r"""
:root{color-scheme:dark;--bg:#0c0f12;--line:rgba(255,255,255,.16);--muted:#aab3bc;--text:#f6f7f8;--hotspot:#fff;--hotspot-fade:140ms}*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}.orbit-viewport{position:relative;width:100%;height:100svh;min-height:520px;overflow:hidden;touch-action:pan-y;user-select:none;background:radial-gradient(circle at 50% 44%,#20262d 0,#101419 60%,#0c0f12 100%);cursor:grab}.orbit-viewport[data-held="true"]{cursor:grabbing}.orbit-frame{display:block;width:100%;height:100%;object-fit:contain;pointer-events:none}.pilot-status{position:absolute;z-index:3;left:18px;top:16px;margin:0;padding:7px 10px;border:1px solid var(--line);border-radius:7px;background:rgba(12,15,18,.72);color:var(--muted);font-size:11px;letter-spacing:.04em;pointer-events:none}.selection-status{position:absolute;z-index:3;left:18px;bottom:16px;margin:0;color:var(--muted);font-size:11px;pointer-events:none}.hotspot[hidden]{display:none!important;pointer-events:none}.hotspot{position:absolute;width:30px;height:30px;transform:translate(-50%,-50%);border:0;background:transparent;color:var(--hotspot);cursor:pointer;padding:0;filter:drop-shadow(0 2px 6px rgba(0,0,0,.45));opacity:0;transition:opacity var(--hotspot-fade) ease-out}.hotspot.is-visible{opacity:1}.hotspot-ring{position:absolute;inset:6px;border:1.5px solid currentColor;border-radius:50%;background:rgba(12,15,18,.36)}.hotspot-ring::after{content:"";position:absolute;inset:4px;border-radius:50%;background:currentColor}.hotspot-pulse{position:absolute;inset:3px;border:1px solid currentColor;border-radius:50%;opacity:.55;animation:hotspotPulse 2.2s ease-out infinite}.hotspot-label{position:absolute;left:27px;top:50%;transform:translate(0,-50%);padding:5px 9px;border:1px solid rgba(255,255,255,.13);border-radius:5px;background:rgba(18,22,27,.78);box-shadow:0 8px 24px rgba(0,0,0,.24);color:#fff;font-size:12px;font-weight:600;line-height:1.2;white-space:nowrap;opacity:1;pointer-events:none;transition:opacity .16s ease,transform .16s ease}.hotspot:focus-visible{outline:2px solid #fff;outline-offset:3px;border-radius:50%}@keyframes hotspotPulse{0%{transform:scale(.72);opacity:.6}75%,100%{transform:scale(1.35);opacity:0}}.audit-spacer{height:120svh;background:linear-gradient(#0c0f12,#080a0c)}@media(max-width:480px){.orbit-viewport:has(.chamber.is-visible):has(.condenser.is-visible) .chamber .hotspot-label{transform:translate(0,calc(-50% - 15px))}.orbit-viewport:has(.chamber.is-visible):has(.condenser.is-visible) .condenser .hotspot-label{transform:translate(0,calc(-50% + 5px))}}@media(prefers-reduced-motion:reduce){.hotspot,.hotspot-label{transition:none}.hotspot-pulse{animation:none}}
""".strip()


PILOT_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>TWINKLE 固定轨道拖拽 Pilot</title><link rel="stylesheet" href="pilot.css"></head>
<body><main id="orbit-viewport" class="orbit-viewport" data-testid="orbit-viewport" data-held="false"><img id="orbit-frame" class="orbit-frame" alt="TWINKLE H2 固定轨道 360° 总览"><p id="pilot-status" class="pilot-status" aria-live="polite">正在验证 96 帧资源</p><p id="selection-status" class="selection-status" aria-live="polite">热点点击只记录选择，不进入聚焦路线</p><button class="hotspot chamber" type="button" data-unit="dual_channel_collection_optics_chamber" aria-label="双通道采集光学舱" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">双通道采集光学舱</span></button><button class="hotspot condenser" type="button" data-unit="dual_channel_condenser_lens_assembly" aria-label="聚光镜组件" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">聚光镜组件</span></button></main><div class="audit-spacer" aria-hidden="true"></div><script src="pilot.js"></script></body></html>
'''


PILOT_JS = r"""
'use strict';
const FRAME_COUNT = 96;
const CLICK_DRAG_THRESHOLD_PX = 6;
const HOTSPOT_SPEED_FACTOR = 0.3;
const HOTSPOT_LEAVE_GRACE_MS = 100;
const SPEED_RECOVERY_MS = 180;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const viewport = document.querySelector('#orbit-viewport');
const frameImage = document.querySelector('#orbit-frame');
const statusLine = document.querySelector('#pilot-status');
const selectionLine = document.querySelector('#selection-status');
const hotspotElements = new Map([...document.querySelectorAll('[data-unit]')].map(element => [element.dataset.unit, element]));
const names = {dual_channel_collection_optics_chamber:'双通道采集光学舱',dual_channel_condenser_lens_assembly:'聚光镜组件'};
const eventLog = [];
const fadeTimers = new Map();
const state = {
  manifest:null, orbitPositionFrames:0, displayedFrame:-1, lastTimestamp:null,
  ready:false, resourceError:false, reducedMotion:reducedMotion.matches,
  viewportVisible:true, documentVisible:document.visibilityState === 'visible', windowFocused:true,
  destroyed:false, overviewActive:true, safePaused:true, safeReasons:['resources-not-ready'],
  currentSpeedFactor:0, targetSpeedFactor:0, speedTransition:null,
  pointer:{activeId:null,held:false,dragging:false,startX:0,startY:0,startPositionFrames:0,viewportWidth:1,suppressNextClick:false,pressHotspotUnit:null,skipCapturedHotspotClick:null},
  hotspotIntent:{hovered:new Set(),focused:new Set(),leaveTimers:new Map()},
  selectedHotspot:null, frameHistory:[]
};
function log(type,detail={}){eventLog.push({type,time:performance.now(),...detail});if(eventLog.length>400)eventLog.shift();}
function wrapFrames(value){return ((value % FRAME_COUNT) + FRAME_COUNT) % FRAME_COUNT;}
function frameIndex(){return Math.floor(wrapFrames(state.orbitPositionFrames)) % FRAME_COUNT;}
function computeSafeReasons(){const reasons=[];if(!state.ready)reasons.push('resources-not-ready');if(state.resourceError)reasons.push('resource-error');if(state.reducedMotion)reasons.push('reduced-motion');if(!state.viewportVisible)reasons.push('viewport-hidden');if(!state.documentVisible)reasons.push('document-hidden');if(!state.windowFocused)reasons.push('window-blurred');if(!state.overviewActive)reasons.push('non-overview');if(state.destroyed)reasons.push('destroyed');return reasons;}
function desiredSpeedFactor(){state.safeReasons=computeSafeReasons();state.safePaused=state.safeReasons.length>0;if(state.safePaused)return 0;if(state.pointer.held)return 0;if(state.hotspotIntent.hovered.size||state.hotspotIntent.focused.size)return HOTSPOT_SPEED_FACTOR;return 1;}
function refreshSpeedIntent(now=performance.now()){const desired=desiredSpeedFactor();if(desired===state.targetSpeedFactor)return;state.targetSpeedFactor=desired;if(desired<state.currentSpeedFactor){state.currentSpeedFactor=desired;state.speedTransition=null;}else{state.speedTransition={from:state.currentSpeedFactor,to:desired,started:now};}log('speed-intent',{desired,safeReasons:[...state.safeReasons]});}
function updateSpeed(now){if(!state.speedTransition)return;const transition=state.speedTransition;const progress=Math.min(1,Math.max(0,(now-transition.started)/SPEED_RECOVERY_MS));const eased=1-(1-progress)*(1-progress);state.currentSpeedFactor=transition.from+(transition.to-transition.from)*eased;if(progress>=1){state.currentSpeedFactor=transition.to;state.speedTransition=null;}}
function clearHotspotIntent(unit){state.hotspotIntent.hovered.delete(unit);state.hotspotIntent.focused.delete(unit);const timer=state.hotspotIntent.leaveTimers.get(unit);if(timer)clearTimeout(timer);state.hotspotIntent.leaveTimers.delete(unit);refreshSpeedIntent();}
function scheduleHotspotVisibility(element,record){const unit=element.dataset.unit,isVisible=record.status==='visible'&&record.eligible===true;clearTimeout(fadeTimers.get(element));fadeTimers.delete(element);element.style.left=(record.projection[0]*100)+'%';element.style.top=(record.projection[1]*100)+'%';if(isVisible){element.hidden=false;element.disabled=false;element.style.pointerEvents='auto';element.setAttribute('aria-hidden','false');requestAnimationFrame(()=>element.classList.add('is-visible'));return;}clearHotspotIntent(unit);element.disabled=true;element.style.pointerEvents='none';element.setAttribute('aria-hidden','true');element.classList.remove('is-visible');if(document.activeElement===element)element.blur();const timer=setTimeout(()=>{if(element.getAttribute('aria-hidden')==='true')element.hidden=true;fadeTimers.delete(element);},140);fadeTimers.set(element,timer);}
function renderFrame(force=false){if(!state.manifest)return;const index=frameIndex();if(!force&&index===state.displayedFrame)return;const record=state.manifest.frames[index];frameImage.src=record.src;state.displayedFrame=index;for(const [unit,hotspot] of Object.entries(record.hotspots))scheduleHotspotVisibility(hotspotElements.get(unit),hotspot);state.frameHistory.push({index,positionFrames:state.orbitPositionFrames,time:performance.now()});if(state.frameHistory.length>240)state.frameHistory.shift();document.body.dataset.frame=String(index);document.body.dataset.angle=String(record.angleDegrees);}
function updateStatus(){statusLine.textContent=`frame-${String(frameIndex()).padStart(3,'0')} · ${Math.round(state.currentSpeedFactor*100)}%`;}
function animationLoop(now){if(state.lastTimestamp===null)state.lastTimestamp=now;const delta=Math.min(100,Math.max(0,now-state.lastTimestamp));state.lastTimestamp=now;refreshSpeedIntent(now);updateSpeed(now);if(state.currentSpeedFactor>0){state.orbitPositionFrames=wrapFrames(state.orbitPositionFrames+delta*FRAME_COUNT/state.manifest.durationMs*state.currentSpeedFactor);renderFrame();}else if(state.manifest){renderFrame();}updateStatus();viewport.dataset.held=String(state.pointer.held);document.body.dataset.speedFactor=state.currentSpeedFactor.toFixed(3);requestAnimationFrame(animationLoop);}
function pointerEligible(event){if(event.button !== 0)return false;if(event.isPrimary === false)return false;return true;}
function onPointerDown(event){if(!pointerEligible(event)||state.pointer.activeId!==null)return;state.pointer.activeId=event.pointerId;state.pointer.held=true;state.pointer.dragging=false;state.pointer.startX=event.clientX;state.pointer.startY=event.clientY;state.pointer.startPositionFrames=state.orbitPositionFrames;state.pointer.viewportWidth=Math.max(1,viewport.getBoundingClientRect().width);state.pointer.suppressNextClick=false;state.pointer.pressHotspotUnit=event.target.closest?.('.hotspot')?.dataset.unit||null;viewport.setPointerCapture(event.pointerId);refreshSpeedIntent();log('pointer-captured',{pointerId:event.pointerId,pointerType:event.pointerType,frame:frameIndex()});}
function onPointerMove(event){if(event.pointerId!==state.pointer.activeId||!state.pointer.held)return;const dx=event.clientX-state.pointer.startX,dy=event.clientY-state.pointer.startY;if(!state.pointer.dragging&&Math.hypot(dx,dy)>CLICK_DRAG_THRESHOLD_PX){state.pointer.dragging=true;state.pointer.suppressNextClick=true;log('drag-start',{frame:frameIndex(),dx,dy});}if(!state.pointer.dragging)return;event.preventDefault();state.orbitPositionFrames=wrapFrames(state.pointer.startPositionFrames-dx/state.pointer.viewportWidth*FRAME_COUNT);renderFrame(true);}
function commitHotspotSelection(unit){state.selectedHotspot={unit,frameIndex:frameIndex()};selectionLine.textContent=`已记录 ${names[unit]} · frame-${String(frameIndex()).padStart(3,'0')}`;log('hotspot-selected',state.selectedHotspot);}
function finishPointer(event,reason){if(event.pointerId!==state.pointer.activeId)return;const pointerId=state.pointer.activeId,wasDragging=state.pointer.dragging,pressHotspotUnit=state.pointer.pressHotspotUnit;state.pointer.activeId=null;state.pointer.held=false;state.pointer.dragging=false;state.pointer.pressHotspotUnit=null;if(viewport.hasPointerCapture(pointerId)&&reason!=='lostpointercapture')viewport.releasePointerCapture(pointerId);if(!wasDragging&&pressHotspotUnit&&reason==='pointerup'){state.pointer.skipCapturedHotspotClick=pressHotspotUnit;commitHotspotSelection(pressHotspotUnit);setTimeout(()=>{state.pointer.skipCapturedHotspotClick=null;},0);}refreshSpeedIntent();log('pointer-release',{reason,wasDragging,frame:frameIndex()});if(state.pointer.suppressNextClick)setTimeout(()=>{state.pointer.suppressNextClick=false;},0);}
viewport.addEventListener('pointerdown',onPointerDown);
viewport.addEventListener('pointermove',onPointerMove,{passive:false});
viewport.addEventListener('pointerup',event=>finishPointer(event,'pointerup'));
viewport.addEventListener('pointercancel',event=>finishPointer(event,'pointercancel'));
viewport.addEventListener('lostpointercapture',event=>finishPointer(event,'lostpointercapture'));
document.addEventListener('click',event=>{if(state.pointer.suppressNextClick&&viewport.contains(event.target)){event.preventDefault();event.stopImmediatePropagation();log('click-suppressed',{frame:frameIndex()});}},true);
for(const [unit,element] of hotspotElements){element.addEventListener('pointerenter',()=>{const record=state.manifest?.frames[frameIndex()]?.hotspots[unit];if(!record?.eligible)return;const timer=state.hotspotIntent.leaveTimers.get(unit);if(timer)clearTimeout(timer);state.hotspotIntent.leaveTimers.delete(unit);state.hotspotIntent.hovered.add(unit);refreshSpeedIntent();log('hotspot-hover',{unit,active:true});});element.addEventListener('pointerleave',()=>{const timer=setTimeout(()=>{state.hotspotIntent.leaveTimers.delete(unit);state.hotspotIntent.hovered.delete(unit);refreshSpeedIntent();log('hotspot-hover',{unit,active:false});},HOTSPOT_LEAVE_GRACE_MS);state.hotspotIntent.leaveTimers.set(unit,timer);});element.addEventListener('focus',()=>{state.hotspotIntent.focused.add(unit);refreshSpeedIntent();log('hotspot-focus',{unit,active:true});});element.addEventListener('blur',()=>{state.hotspotIntent.focused.delete(unit);refreshSpeedIntent();log('hotspot-focus',{unit,active:false});});element.addEventListener('click',()=>{if(state.pointer.skipCapturedHotspotClick===unit){state.pointer.skipCapturedHotspotClick=null;return;}commitHotspotSelection(unit);});}
const intersectionObserver=new IntersectionObserver(entries=>{const entry=entries[entries.length-1];state.viewportVisible=Boolean(entry&&entry.isIntersecting&&entry.intersectionRatio>=0.15);refreshSpeedIntent();log('viewport-visibility',{visible:state.viewportVisible,ratio:entry?.intersectionRatio||0});},{threshold:[0,0.15,0.5]});intersectionObserver.observe(viewport);
document.addEventListener('visibilitychange',()=>{state.documentVisible=document.visibilityState==='visible';refreshSpeedIntent();log('document-visibility',{visible:state.documentVisible});});
addEventListener('blur',()=>{state.windowFocused=false;refreshSpeedIntent();log('window-focus',{focused:false});});
addEventListener('focus',()=>{state.windowFocused=true;refreshSpeedIntent();log('window-focus',{focused:true});});
reducedMotion.addEventListener('change',event=>{state.reducedMotion=event.matches;if(event.matches)state.orbitPositionFrames=0;refreshSpeedIntent();renderFrame(true);});
addEventListener('pagehide',()=>{state.destroyed=true;intersectionObserver.disconnect();for(const timer of fadeTimers.values())clearTimeout(timer);for(const timer of state.hotspotIntent.leaveTimers.values())clearTimeout(timer);clearHotspotIntent();refreshSpeedIntent();log('pagehide');},{once:true});
function preloadFrame(record){return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>{const decoded=typeof image.decode==='function'?image.decode().catch(()=>undefined):Promise.resolve();decoded.then(()=>resolve(record));};image.onerror=()=>reject(new Error('resource-error frame-'+String(record.index).padStart(3,'0')));image.src=record.src;});}
fetch('pilot-manifest.json').then(response=>{if(!response.ok)throw new Error('manifest '+response.status);return response.json();}).then(manifest=>{if(manifest.frameCount!==FRAME_COUNT||manifest.durationMs!==8000||manifest.direction!=='forward')throw new Error('manifest orbit contract drift');state.manifest=manifest;state.orbitPositionFrames=0;renderFrame(true);return Promise.all(manifest.frames.map(preloadFrame));}).then(()=>{state.ready=true;statusLine.textContent='96 帧就绪';refreshSpeedIntent();log('resources-ready',{frameCount:FRAME_COUNT});}).catch(error=>{state.resourceError=true;statusLine.textContent='资源失败，已安全暂停';refreshSpeedIntent();log('resource-error',{message:error.message});console.error(error);});
window.__twinklePilot={snapshot:()=>({frameIndex:frameIndex(),orbitPositionFrames:state.orbitPositionFrames,currentSpeedFactor:state.currentSpeedFactor,targetSpeedFactor:state.targetSpeedFactor,safePaused:state.safePaused,safeReasons:[...state.safeReasons],held:state.pointer.held,dragging:state.pointer.dragging,selectedHotspot:state.selectedHotspot,hovered:[...state.hotspotIntent.hovered],focused:[...state.hotspotIntent.focused],ready:state.ready,resourceError:state.resourceError,viewportVisible:state.viewportVisible,documentVisible:state.documentVisible,windowFocused:state.windowFocused,reducedMotion:state.reducedMotion,displayedSource:state.manifest?.frames[state.displayedFrame]?.src||null,displayedHotspots:state.manifest?.frames[state.displayedFrame]?.hotspots||null}),events:()=>eventLog.map(record=>({...record})),frameHistory:()=>state.frameHistory.map(record=>({...record}))};
requestAnimationFrame(animationLoop);
""".strip()


def _pilot_manifest(authority: dict) -> dict:
    return {
        "schema": "twinkle-stage5-fixed-orbit-drag-pilot-v1",
        "authority": {
            "registrySha256": authority["registrySha256"],
            "c360ManifestSha256": authority["c360ManifestSha256"],
        },
        "frameCount": FRAME_COUNT,
        "durationMs": ORBIT_DURATION_MS,
        "direction": PLAYBACK_DIRECTION,
        "angleStepDegrees": ANGLE_STEP_DEGREES,
        "frames": [
            {
                "index": index,
                "angleDegrees": record["angleDegrees"],
                "src": f"frames/frame-{index:03d}.png",
                "sha256": record["sha256"],
                "bytes": record["bytes"],
                "hotspots": record["hotspots"],
            }
            for index, record in authority["frames"].items()
        ],
    }


def assemble_pilot(staging: Path, authority: dict) -> dict:
    staging = Path(staging).resolve()
    if staging.exists() and any(staging.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty pilot staging: {staging}")
    frames_root = staging / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    copied_bytes = 0
    for index in range(FRAME_COUNT):
        source = authority["frames"][index]
        target = frames_root / f"frame-{index:03d}.png"
        shutil.copyfile(source["path"], target)
        if sha256(target) != source["sha256"] or target.stat().st_size != source["bytes"]:
            raise PilotValidationError(f"copied C360 frame drift: {index:03d}")
        copied_bytes += target.stat().st_size
    manifest = _pilot_manifest(authority)
    _write_json(staging / "pilot-manifest.json", manifest)
    (staging / "index.html").write_text(PILOT_HTML, encoding="utf-8")
    (staging / "pilot.css").write_text(PILOT_CSS + "\n", encoding="utf-8")
    (staging / "pilot.js").write_text(PILOT_JS + "\n", encoding="utf-8")
    report = {
        "schema": "twinkle-stage5-fixed-orbit-drag-machine-results-v1",
        "machinePassed": True,
        "registrySha256": authority["registrySha256"],
        "c360ManifestSha256": authority["c360ManifestSha256"],
        "frameCount": FRAME_COUNT,
        "trackStateCount": FRAME_COUNT,
        "outsideTrackStateCount": 0,
        "orbitDurationMs": ORBIT_DURATION_MS,
        "playbackDirection": PLAYBACK_DIRECTION,
        "seam": "095->000",
        "copiedFrameBytes": copied_bytes,
        "singleTimelineAuthority": True,
        "pointerEvents": True,
        "pointerCapture": True,
        "touchAction": "pan-y",
        "normalSpeedFactor": 1.0,
        "hotspotSpeedFactor": HOTSPOT_SPEED_FACTOR,
        "heldSpeedFactor": 0.0,
        "clickDragThresholdCssPx": CLICK_DRAG_THRESHOLD_PX,
        "hotspotLeaveGraceMs": HOTSPOT_LEAVE_GRACE_MS,
        "speedRecoveryMs": SPEED_RECOVERY_MS,
        "formalAssetWrites": 0,
        "thirdPartyRuntimeDependencies": [],
        "formalIntegrationAuthorized": False,
        "focusViewportImplemented": False,
        "browserAcceptancePending": True,
    }
    _write_json(staging / "machine-results.json", report)
    return report


def build_pilot(repo: Path, output_root: Path) -> dict:
    repo = Path(repo).resolve()
    output_root = validate_output_root(repo, output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite fixed-orbit pilot: {output_root}")
    authority = load_authority(repo)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".twinkle-stage5-fixed-orbit-drag-pilot-", dir=output_root.parent)
    ).resolve()
    try:
        report = assemble_pilot(staging, authority)
        staging.rename(output_root)
        return report
    except Exception:
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output_root = args.output_root or repo / "output" / "twinkle-stage5-fixed-orbit-drag-pilot"
    print(json.dumps(build_pilot(repo, output_root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
