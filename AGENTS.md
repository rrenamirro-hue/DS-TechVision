# DS TechVision — Engineering Instructions

## Product goal

DS TechVision is an independent technician-assistance system.

Current target:
Canon imageRUNNER 1643i / 1643iF.

Primary flow:

CAMERA
→ recognize equipment
→ recognize view
→ recognize visual state
→ localize relevant component
→ track component
→ overlay guidance
→ OEM evidence
→ technician confirmation

## Current milestone

DS-TECHVISION-0.6.1-TRACKING-ENGINE

Current priority:
stable markerless tracking.

Target pipeline:

ORB/RANSAC acquisition
→ target lock
→ Lucas-Kanade optical flow
→ homography update
→ smoothing
→ overlay
→ ORB reacquisition when tracking is lost.

Do NOT implement component segmentation yet.

## Current architecture

Global recognition:
CLIP + OCR.

Fine localization:
JSFeat ORB + RANSAC + homography.

Text retrieval:
intfloat/multilingual-e5-small.

Technical authority:
Canon OEM Service Manual and Parts Catalog.

Digital Twin:
LAB / approximate only.

## Mandatory rules

NO QR.
NO color fiducials.
NO BarcodeDetector.
NO artificial markers.

Do not replace multilingual-e5-small.
Do not reintroduce TF-IDF.

Do not modify PortalBrain.
Do not modify SGS.

Do not modify OEM PDF originals.

Do not use Digital Twin approximate coordinates as physical AR truth.

Never invent:
- screws
- connectors
- part numbers
- quantities
- procedures
- metric positions
- movement distances
- removal directions

OEM documentation remains technical authority.

## Vision semantics

Equipment recognition and procedure guidance are separate.

Camera recognition must continue from procedure step 1.

The procedure determines which recognized object should be emphasized.
It must not determine whether the equipment recognizer runs.

## Known limitation

ComponentRecognizer is NOT currently a real visual component detector.

It currently exposes OEM anchors tied to a recognized reference and
procedure context.

Do not describe this as real component detection.

## Tracking objective

ORB is for acquisition and reacquisition.

After successful acquisition:
track stable keypoints frame-by-frame using optical flow.

Do not execute expensive recognition on every frame.

If tracking quality becomes insufficient:

TRACKING_LOST
→ remove unsafe overlay immediately
→ attempt ORB reacquisition.

## Fail-closed rule

If localization confidence is insufficient,
do not display an exact component position.

Show OEM fallback instead.

## Scope 0.6.1

DO NOT add:

- MediaPipe segmentation
- MobileSAM
- LightGlue
- YOLO
- ARCore
- Unity
- Vuforia
- new printer models
- Digital Twin improvements
- database migrations
- reports or roles

## Verification gates

ACQUIRE
TRACK
TRACKING_LOST
OVERLAY_CLEAR
REACQUIRE
WRONG_REFERENCE_REJECTED
OEM_TRACEABILITY_UNCHANGED
PROCEDURE_PROGRESS_UNCHANGED

Desktop synthetic tests are not proof of Android camera behavior.

Never report Android PASS without Android camera evidence.
