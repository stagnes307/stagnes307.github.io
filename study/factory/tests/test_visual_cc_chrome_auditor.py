from __future__ import annotations

import functools
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUDITOR = ROOT / "factory" / "scripts" / "audit_visual_cc_chrome.mjs"


def _chrome_available() -> bool:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    return any(candidate and Path(candidate).is_file() for candidate in candidates)


@unittest.skipUnless(shutil.which("node") and _chrome_available(), "Node and Chrome are required")
class VisualCcChromeAuditorTests(unittest.TestCase):
    def test_marker_polygon_and_overflow_visible_child_paint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            web_root = Path(temporary)
            curriculum = web_root / "study" / "curricula" / "fixture-course.json"
            lesson = (
                web_root
                / "study"
                / "courses"
                / "fixture-course"
                / "lessons"
                / "1-1-1-1-marker-polygon"
                / "cc.html"
            )
            curriculum.parent.mkdir(parents=True)
            lesson.parent.mkdir(parents=True)
            curriculum.write_text(
                json.dumps(
                    {
                        "course_id": "fixture-course",
                        "title": "Chrome auditor fixture",
                        "sections": [
                            {
                                "units": [
                                    {
                                        "lessons": [
                                            {
                                                "sublessons": [
                                                    {
                                                        "id": "1-1-1-1",
                                                        "slug": "marker-polygon",
                                                        "title": "Marker and polygon",
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            limit_points = " ".join(
                f"{10 + index * 0.5:.1f},610" for index in range(515)
            )
            stroke_path_4096 = (
                "M10 10 H310 V15 H10 V20 H310 V25 H10 V30 H310 V35 H10 "
                "V40 H310 V45 H10 V50 H310 V55 H10 V60 H310 V65 H10 V70 "
                "H310 V205"
            )
            stroke_path_4097 = stroke_path_4096.removesuffix("V205") + "V206"
            budget_paths = "\n".join(
                f'<path id="budget-stroke-{index + 1}" d="{stroke_path_4096}" '
                'fill="none" stroke="#64748b" stroke-width="1"></path>'
                for index in range(25)
            )
            pair_budget_texts = "\n".join(
                f'<text x="5" y="{20 + index * 20}" font-size="12">T{index}</text>'
                for index in range(450)
            )
            lesson.write_text(
                """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>Marker and polygon fixture</title>
<style>
html, body { margin: 0; padding: 0; }
.frame { box-sizing: border-box; margin: 8px; width: 330px; }
svg { display: block; }
.escape { box-sizing: border-box; width: 200px; overflow: hidden; }
.visible-safe { box-sizing: border-box; width: 200px; overflow: visible; }
.marker-solid-source { fill: #0f766e; }
.marker-ring-source { fill: none; stroke: #7c3aed; stroke-width: 2; }
</style>
</head>
<body>
<main class="frame">
  <svg aria-label="marker and polygon cases" width="320" height="640" viewBox="0 0 320 640">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5"
      orient="auto-start-reverse" markerUnits="strokeWidth">
      <path d="M0 0 L10 5 L0 10 Z" fill="#b91c1c"></path>
    </marker>
    <marker id="tight" markerWidth="4" markerHeight="4" refX="4" refY="2"
      orient="auto" markerUnits="userSpaceOnUse">
      <path d="M0 -4 L8 2 L0 8 Z" fill="#be123c"></path>
    </marker>
    <marker id="round-tight" markerWidth="20" markerHeight="20" refX="10" refY="10"
      orient="auto" markerUnits="userSpaceOnUse">
      <circle cx="10" cy="10" r="13.5" fill="none" stroke="#7c3aed" stroke-width="2"></circle>
    </marker>
    <marker id="use-solid" markerWidth="30" markerHeight="30" refX="15" refY="15"
      orient="auto" markerUnits="userSpaceOnUse" overflow="visible">
      <defs><circle id="solid-source" class="marker-solid-source" cx="15" cy="15" r="13"></circle></defs>
      <use href="#solid-source"></use>
    </marker>
    <marker id="use-ring" markerWidth="80" markerHeight="80" refX="40" refY="40"
      orient="auto" markerUnits="userSpaceOnUse" overflow="visible">
      <defs><circle id="ring-source" class="marker-ring-source" cx="40" cy="40" r="35"></circle></defs>
      <use href="#ring-source"></use>
    </marker>
  </defs>
  <polyline points="30,40 150,40 280,40" fill="none" stroke="#1d4ed8" stroke-width="2"
    marker-start="url(#arrow)" marker-mid="url(#arrow)" marker-end="url(#arrow)"></polyline>
  <text x="138" y="46" font-size="24">MID HIT</text>
  <line x1="250" y1="82" x2="319" y2="82" stroke="#1d4ed8" stroke-width="2"
    marker-end="url(#arrow)"></line>
  <line x1="20" y1="92" x2="100" y2="92" stroke="#be123c" stroke-width="2"
    marker-end="url(#tight)"></line>
  <polygon points="40,115 118,145 40,175" fill="#ea580c"></polygon>
  <text x="78" y="151" font-size="24">POLY HIT</text>
  <polygon points="175,105 245,140 175,175 105,140" fill="#dbeafe"></polygon>
  <text x="145" y="147" font-size="20">SAFE</text>
  <text x="138" y="202" font-size="20">PATH MID</text>
  <path d="M30 195 L150 195 L150 215" fill="none" stroke="#0369a1" stroke-width="2"
    marker-mid="url(#arrow)"></path>
  <line x1="260" y1="240" x2="300" y2="280" stroke="#7c3aed" stroke-width="2"
    marker-start="url(#round-tight)"></line>
  <text x="246" y="234" font-size="12" data-text-role="auxiliary">R</text>
  <text x="72" y="340" font-size="18">FILL COVER</text>
  <polygon points="55,310 235,310 235,355 55,355" fill="#dc2626"></polygon>
  <polygon points="55,365 235,365 235,410 55,410" fill="#dbeafe"></polygon>
  <text x="72" y="395" font-size="18">BEHIND SAFE</text>
  <text x="67" y="452" font-size="18">USE HIT</text>
  <line x1="80" y1="446" x2="180" y2="446" stroke="#0f766e" stroke-width="2"
    marker-start="url(#use-solid)"></line>
  <text x="132" y="510" font-size="12" data-text-role="auxiliary">USE SAFE</text>
  <line x1="160" y1="506" x2="250" y2="506" stroke="#7c3aed" stroke-width="2"
    marker-start="url(#use-ring)"></line>
  <text x="61" y="557" font-size="18">A</text>
  <text x="131" y="557" font-size="18">B</text>
  <path d="M30 550 L70 550 M140 550 L180 550" fill="none" stroke="#0369a1"
    stroke-width="2" marker-mid="url(#arrow)"></path>
  <polyline points="__LIMIT_POINTS__" fill="none" stroke="#64748b" stroke-width="1"
    marker-mid="url(#arrow)"></polyline>
</svg>
<svg id="clip-regression" aria-label="ancestor clip path cases" width="320" height="100"
  viewBox="0 0 320 100">
  <defs>
    <clipPath id="chart-clip"><rect x="20" y="10" width="260" height="50"></rect></clipPath>
  </defs>
  <g clip-path="url(#chart-clip)">
    <path id="clipped-chart-path" d="M20 35 C120 5 240 75 370 35" fill="none"
      stroke="#2563eb" stroke-width="3"></path>
  </g>
  <path id="unclipped-control-path" d="M20 82 H370" fill="none"
    stroke="#dc2626" stroke-width="3"></path>
</svg>
<svg id="root-clip-regression" aria-label="root clip path case" width="320" height="80"
  viewBox="0 0 320 80" clip-path="url(#root-chart-clip)">
  <defs>
    <clipPath id="root-chart-clip"><rect x="20" y="10" width="260" height="55"></rect></clipPath>
  </defs>
  <path id="root-clipped-chart-path" d="M20 38 C130 3 250 73 370 38" fill="none"
    stroke="#0284c7" stroke-width="3"></path>
</svg>
<svg id="object-clip-regression" aria-label="object bounding box clip path case"
  width="320" height="80" viewBox="0 0 320 80">
  <defs>
    <clipPath id="object-chart-clip" clipPathUnits="objectBoundingBox">
      <rect x="0" y="0" width="0.74" height="1"></rect>
    </clipPath>
  </defs>
  <g clip-path="url(#object-chart-clip)">
    <path id="object-clipped-chart-path" d="M20 38 C130 3 250 73 370 38" fill="none"
      stroke="#0f766e" stroke-width="3"></path>
  </g>
</svg>
<svg id="collision-clip-regression" aria-label="clipped collision paint cases"
  width="320" height="150" viewBox="0 0 320 150">
  <defs>
    <clipPath id="collision-left-clip"><rect x="0" y="0" width="80" height="150"></rect></clipPath>
  </defs>
  <text id="clipped-away-text" x="0" y="45" font-size="24"
    clip-path="url(#collision-left-clip)">CLIPPED AWAY TEXT WIDE</text>
  <path id="text-clip-safe-line" d="M100 36 H310" fill="none"
    stroke="#2563eb" stroke-width="3"></path>
  <g clip-path="url(#collision-left-clip)">
    <path id="geometry-clip-safe-line" d="M0 86 H310" fill="none"
      stroke="#0f766e" stroke-width="3"></path>
  </g>
  <text x="100" y="94" font-size="24">GEOMETRY CLIP SAFE</text>
  <text x="100" y="137" font-size="18">FILL CLIP SAFE</text>
  <polygon id="fill-clip-safe-polygon" points="0,110 310,110 310,145 0,145"
    clip-path="url(#collision-left-clip)" fill="#dc2626"></polygon>
</svg>
<svg id="occlusion-regression" aria-label="later opaque paint cases" width="320" height="310"
  viewBox="0 0 320 310">
  <defs>
    <clipPath id="occluder-islands">
      <rect x="60" y="164" width="42" height="55"></rect>
      <rect x="268" y="164" width="42" height="55"></rect>
    </clipPath>
  </defs>
  <path id="occluded-stroke" d="M20 45 H300" fill="none"
    stroke="#111827" stroke-width="2"></path>
  <rect x="60" y="18" width="250" height="55" fill="#ffffff"></rect>
  <text x="85" y="53" font-size="24">OCCLUDED SAFE</text>
  <path id="visible-stroke" d="M20 118 H300" fill="none"
    stroke="#111827" stroke-width="2"></path>
  <rect x="60" y="91" width="250" height="55" fill="#ffffff"
    fill-opacity="0.45"></rect>
  <text x="85" y="126" font-size="24">VISIBLE HIT</text>
  <path id="clip-gap-stroke" d="M20 191 H300" fill="none"
    stroke="#111827" stroke-width="2"></path>
  <g clip-path="url(#occluder-islands)">
    <rect x="60" y="164" width="250" height="55" fill="#ffffff"></rect>
  </g>
  <text x="112" y="199" font-size="24">CLIP GAP HIT</text>
  <path id="modern-alpha-stroke" d="M20 264 H300" fill="none"
    stroke="#111827" stroke-width="2"></path>
  <rect x="60" y="237" width="250" height="55"
    fill="color(srgb 1 1 1 / 0.4)"></rect>
  <text x="85" y="272" font-size="24">ALPHA HIT</text>
</svg>
<svg id="stroke-cap-accepted" aria-label="4096 stroke samples accepted" width="320" height="220"
  viewBox="0 0 320 220">
  <path id="stroke-samples-4096" d="__STROKE_PATH_4096__" fill="none"
    stroke="#475569" stroke-width="1"></path>
</svg>
<svg id="stroke-cap-rejected" aria-label="4097 stroke samples rejected" width="320" height="220"
  viewBox="0 0 320 220">
  <path id="stroke-samples-4097" d="__STROKE_PATH_4097__" fill="none"
    stroke="#475569" stroke-width="1"></path>
</svg>
<svg id="total-budget-regression" aria-label="total SVG sample budget retained"
  width="320" height="220" viewBox="0 0 320 220">
  __BUDGET_PATHS__
</svg>
<svg id="pair-budget-regression" aria-label="collision pair inspection budget"
  width="320" height="9200" viewBox="0 0 320 9200">
  __PAIR_BUDGET_TEXTS__
</svg>
<div class="escape">
  <div class="visible-safe">
  <svg aria-label="overflow visible embedded child" width="200" height="90" viewBox="0 0 200 90"
    style="overflow: visible">
    <defs><symbol id="escape-shape"><rect width="65" height="20" fill="#7c3aed"></rect></symbol></defs>
    <use href="#escape-shape" x="180" y="4"></use>
    <image x="180" y="32" width="65" height="20"
      href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='65' height='20'%3E%3Crect width='65' height='20' fill='%230ea5e9'/%3E%3C/svg%3E"></image>
    <foreignObject x="180" y="60" width="65" height="20"><div xmlns="http://www.w3.org/1999/xhtml" style="width:65px;height:20px;background:#f59e0b"></div></foreignObject>
  </svg>
  </div>
</div>
<div class="visible-safe">
  <svg aria-label="harmless overflow visible embedded child" width="200" height="90"
    viewBox="0 0 200 90" style="overflow: visible">
    <defs><symbol id="safe-shape"><rect width="65" height="20" fill="#16a34a"></rect></symbol></defs>
    <use href="#safe-shape" x="180" y="4"></use>
    <image x="180" y="32" width="65" height="20"
      href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='65' height='20'%3E%3Crect width='65' height='20' fill='%2316a34a'/%3E%3C/svg%3E"></image>
    <foreignObject x="180" y="60" width="65" height="20"><div xmlns="http://www.w3.org/1999/xhtml" style="width:65px;height:20px;background:#16a34a"></div></foreignObject>
  </svg>
</div>
</main>
</body>
</html>
""".replace("__LIMIT_POINTS__", limit_points)
                .replace("__STROKE_PATH_4096__", stroke_path_4096)
                .replace("__STROKE_PATH_4097__", stroke_path_4097)
                .replace("__BUDGET_PATHS__", budget_paths)
                .replace("__PAIR_BUDGET_TEXTS__", pair_budget_texts),
                encoding="utf-8",
            )

            handler = functools.partial(
                http.server.SimpleHTTPRequestHandler,
                directory=str(web_root),
            )
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            report_path = web_root / "audit.json"
            try:
                completed = subprocess.run(
                    [
                        shutil.which("node") or "node",
                        str(AUDITOR),
                        "--base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--target",
                        "fixture-course:1-1-1-1",
                        "--concurrency",
                        "2",
                        "--output",
                        str(report_path),
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    timeout=60,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(1, completed.returncode, completed.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(3, report["schemaVersion"])
            self.assertEqual(4_096, report["thresholds"]["strokeMaximumSamplePointsPerGeometry"])
            self.assertEqual(512, report["thresholds"]["markerMaximumPlacementsPerPosition"])
            self.assertEqual(100_000, report["thresholds"]["totalMaximumSamplePointsPerSvg"])
            self.assertEqual(
                100_000,
                report["thresholds"]["collisionMaximumPairInspectionsPerSvg"],
            )
            self.assertEqual(
                500,
                report["thresholds"]["collisionMaximumResultsPerKindPerSvg"],
            )
            self.assertEqual(2, report["summary"]["renderedCaseCount"])
            self.assertEqual(0, report["summary"]["auditorOrNavigationErrorCaseCount"])
            self.assertEqual(0, report["summary"]["runtimeErrorCount"])
            self.assertEqual(2, report["summary"]["collisionAuditErrorCount"])
            self.assertEqual(
                2,
                report["summary"]["exhaustedSvgCollisionPairBudgetCount"],
            )
            self.assertEqual(4, report["summary"]["geometrySamplingErrorCount"])
            self.assertGreaterEqual(report["summary"]["markerGeometrySamplingErrorCount"], 2)
            self.assertEqual(0, report["summary"]["polygonGeometrySamplingErrorCount"])
            self.assertGreaterEqual(report["summary"]["markerPaintItemCount"], 12)
            self.assertGreaterEqual(report["summary"]["markerInstanceCount"], 14)
            self.assertGreaterEqual(report["summary"]["clippedMarkerPaintCount"], 2)
            self.assertGreaterEqual(report["summary"]["internallyClippedMarkerPaintCount"], 4)
            self.assertGreaterEqual(report["summary"]["markerTextCollisionCount"], 6)
            self.assertGreaterEqual(report["summary"]["polygonTextCollisionCount"], 2)
            self.assertGreaterEqual(report["summary"]["embeddedPaintItemCount"], 12)
            self.assertEqual(0, report["summary"]["clippedEmbeddedPaintItemCount"])
            self.assertGreaterEqual(report["summary"]["svgPaintObstructedWrapperCount"], 2)
            self.assertGreaterEqual(report["summary"]["svgPaintEscapingWrapperCount"], 2)

            for result in report["results"]:
                self.assertIn(result["viewport"]["width"], {360, 390})
                metrics = result["metrics"]
                self.assertFalse(metrics["pageHorizontalOverflow"]["failed"])
                self.assertGreaterEqual(metrics["markerPaintItemCount"], 6)
                self.assertGreaterEqual(metrics["markerInstanceCount"], 7)
                self.assertGreaterEqual(metrics["clippedMarkerPaintCount"], 1)
                self.assertGreaterEqual(metrics["internallyClippedMarkerPaintCount"], 2)
                self.assertGreaterEqual(metrics["markerTextCollisionCount"], 3)
                self.assertGreaterEqual(metrics["polygonTextCollisionCount"], 1)
                self.assertGreaterEqual(metrics["embeddedPaintItemCount"], 6)
                self.assertEqual(0, metrics["clippedEmbeddedPaintItemCount"])
                self.assertGreaterEqual(metrics["svgPaintObstructedWrapperCount"], 1)
                self.assertGreaterEqual(metrics["svgPaintEscapingWrapperCount"], 1)
                self.assertEqual(
                    metrics["svgPaintObstructedWrapperCount"],
                    metrics["svgPaintEscapingWrapperCount"],
                )
                svgs_by_selector = {svg["selector"]: svg for svg in metrics["svgs"]}
                clip_svg = svgs_by_selector["svg#clip-regression"]
                clipped_geometry_selectors = {
                    item["selector"]
                    for item in clip_svg["paintClipping"]["clippedPaintItems"]
                    if item["kind"] == "geometry"
                }
                self.assertIn("path#unclipped-control-path", clipped_geometry_selectors)
                self.assertNotIn("path#clipped-chart-path", clipped_geometry_selectors)
                root_clip_svg = svgs_by_selector["svg#root-clip-regression"]
                root_clipped_selectors = {
                    item["selector"]
                    for item in root_clip_svg["paintClipping"]["clippedPaintItems"]
                    if item["kind"] == "geometry"
                }
                self.assertNotIn("path#root-clipped-chart-path", root_clipped_selectors)
                object_clip_svg = svgs_by_selector["svg#object-clip-regression"]
                object_clipped_selectors = {
                    item["selector"]
                    for item in object_clip_svg["paintClipping"]["clippedPaintItems"]
                    if item["kind"] == "geometry"
                }
                self.assertNotIn("path#object-clipped-chart-path", object_clipped_selectors)

                collision_clip_svg = svgs_by_selector["svg#collision-clip-regression"]
                clipped_text = next(
                    text
                    for text in collision_clip_svg["textMetrics"]["texts"]
                    if text["selector"] == "text#clipped-away-text"
                )
                self.assertLessEqual(clipped_text["rect"]["width"], 80.01)
                clipped_collision_selectors = {
                    collision["geometrySelector"]
                    for collision in (
                        collision_clip_svg["linePathTextCollisions"]
                        + collision_clip_svg["polygonTextCollisions"]
                    )
                }
                self.assertNotIn("path#text-clip-safe-line", clipped_collision_selectors)
                self.assertNotIn("path#geometry-clip-safe-line", clipped_collision_selectors)
                self.assertNotIn("polygon#fill-clip-safe-polygon", clipped_collision_selectors)

                pair_budget_svg = svgs_by_selector["svg#pair-budget-regression"]
                self.assertEqual(
                    {
                        "used": 100_000,
                        "limit": 100_000,
                        "exhausted": True,
                        "remaining": 0,
                    },
                    pair_budget_svg["collisionPairInspectionBudget"],
                )
                self.assertEqual(1, pair_budget_svg["collisionAuditErrorCount"])
                pair_limit = pair_budget_svg["collisionAuditErrors"][0]["samplingLimit"]
                self.assertEqual("collision-pair-inspection-limit", pair_limit["code"])
                self.assertEqual(100_001, pair_limit["observed"])
                self.assertEqual(100_000, pair_limit["limit"])

                occlusion_svg = svgs_by_selector["svg#occlusion-regression"]
                occlusion_collisions = occlusion_svg["linePathTextCollisions"]
                self.assertTrue(any(
                    collision["geometrySelector"] == "path#visible-stroke"
                    and collision["textExcerpt"] == "VISIBLE HIT"
                    for collision in occlusion_collisions
                ))
                self.assertFalse(any(
                    collision["geometrySelector"] == "path#occluded-stroke"
                    and collision["textExcerpt"] == "OCCLUDED SAFE"
                    for collision in occlusion_collisions
                ))
                self.assertTrue(any(
                    collision["geometrySelector"] == "path#clip-gap-stroke"
                    and collision["textExcerpt"] == "CLIP GAP HIT"
                    for collision in occlusion_collisions
                ))
                self.assertTrue(any(
                    collision["geometrySelector"] == "path#modern-alpha-stroke"
                    and collision["textExcerpt"] == "ALPHA HIT"
                    for collision in occlusion_collisions
                ))

                accepted_stroke_svg = svgs_by_selector["svg#stroke-cap-accepted"]
                self.assertEqual(4_096, accepted_stroke_svg["samplePointBudget"]["used"])
                self.assertEqual([], accepted_stroke_svg["geometrySamplingErrors"])

                rejected_stroke_svg = svgs_by_selector["svg#stroke-cap-rejected"]
                rejected_limits = [
                    error["samplingLimit"]
                    for error in rejected_stroke_svg["geometrySamplingErrors"]
                ]
                self.assertEqual(1, len(rejected_limits))
                self.assertEqual("stroke-sample-point-limit", rejected_limits[0]["code"])
                self.assertEqual(4_097, rejected_limits[0]["observed"])
                self.assertEqual(4_096, rejected_limits[0]["limit"])

                budget_svg = svgs_by_selector["svg#total-budget-regression"]
                self.assertTrue(budget_svg["samplePointBudget"]["exhausted"])
                self.assertEqual(98_304, budget_svg["samplePointBudget"]["used"])
                budget_limits = [
                    error["samplingLimit"]
                    for error in budget_svg["geometrySamplingErrors"]
                ]
                self.assertEqual(1, len(budget_limits))
                self.assertEqual("svg-sample-point-limit", budget_limits[0]["code"])
                self.assertEqual(102_400, budget_limits[0]["observed"])
                self.assertEqual(100_000, budget_limits[0]["limit"])
                obstructed_wrappers = metrics["svgPaintObstructedWrappers"]
                self.assertTrue(obstructed_wrappers)
                self.assertTrue(all(".escape" in item["selector"]
                                    for item in obstructed_wrappers))
                self.assertFalse(any(".visible-safe" in item["selector"]
                                     for item in obstructed_wrappers))
                obstructed_items = [
                    item
                    for wrapper in obstructed_wrappers
                    for item in wrapper["paintOutsideInnerClientBoxItems"]
                ]
                self.assertTrue(any("use" in item["selector"] for item in obstructed_items))
                self.assertTrue(any("image" in item["selector"] for item in obstructed_items))
                self.assertTrue(any("foreignobject" in item["selector"]
                                    for item in obstructed_items))
                marker_sampling_errors = [
                    error
                    for svg in metrics["svgs"]
                    for error in svg["markerGeometrySamplingErrors"]
                ]
                placement_limits = [
                    error["samplingLimit"]
                    for error in marker_sampling_errors
                    if error.get("samplingLimit", {}).get("code")
                    == "marker-placement-limit"
                ]
                self.assertTrue(placement_limits)
                self.assertTrue(all(limit["observed"] > limit["limit"]
                                    for limit in placement_limits))
                rotated_clipped_markers = [
                    item
                    for svg in metrics["svgs"]
                    for item in svg["internallyClippedMarkerPaintItems"]
                    if item.get("marker", {}).get("id") == "round-tight"
                ]
                self.assertTrue(rotated_clipped_markers)
                self.assertTrue(any(abs(item["marker"]["angleDeg"] - 45) < 0.5
                                    for item in rotated_clipped_markers))
                self.assertTrue(all(len(item["markerViewportQuad"]) == 4
                                    for item in rotated_clipped_markers))
                marker_collisions = [
                    collision
                    for svg in metrics["svgs"]
                    for collision in svg["markerTextCollisions"]
                ]
                self.assertTrue(marker_collisions)
                self.assertTrue(any(collision.get("marker", {}).get("position") == "mid"
                                    for collision in marker_collisions))
                self.assertTrue(any(collision["textExcerpt"] == "PATH MID"
                                    for collision in marker_collisions))
                use_fill_collisions = [
                    collision
                    for collision in marker_collisions
                    if collision["textExcerpt"] == "USE HIT"
                    and collision["geometryTag"] == "marker-use"
                ]
                self.assertTrue(use_fill_collisions)
                self.assertTrue(any("filled-paint" in collision["collisionModes"]
                                    for collision in use_fill_collisions))
                self.assertTrue(all(collision["fillSampling"]["paintHitTestFallbackUsed"]
                                    for collision in use_fill_collisions))
                self.assertFalse(any(collision["textExcerpt"] == "USE SAFE"
                                     for collision in marker_collisions))
                subpath_mid_points = {
                    round(collision["marker"]["point"]["x"])
                    for collision in marker_collisions
                    if collision["textExcerpt"] in {"A", "B"}
                    and collision.get("marker", {}).get("position") == "mid"
                }
                self.assertEqual({70, 140}, subpath_mid_points)
                path_mid_collisions = [
                    collision for collision in marker_collisions
                    if collision["textExcerpt"] == "PATH MID"
                ]
                self.assertTrue(any(abs(collision["marker"]["angleDeg"] - 45) < 0.5
                                    for collision in path_mid_collisions))
                polygon_collisions = [
                    collision
                    for svg in metrics["svgs"]
                    for collision in svg["polygonTextCollisions"]
                ]
                fill_cover_collisions = [
                    collision
                    for collision in polygon_collisions
                    if collision["textExcerpt"] == "FILL COVER"
                ]
                self.assertTrue(fill_cover_collisions)
                self.assertTrue(any(collision["collisionModes"] == ["filled-paint"]
                                    for collision in fill_cover_collisions))
                self.assertFalse(any(collision["textExcerpt"] == "BEHIND SAFE"
                                     for collision in polygon_collisions))
                all_geometry_collisions = [
                    collision
                    for svg in metrics["svgs"]
                    for collision in (
                        svg["linePathTextCollisions"]
                        + svg["markerTextCollisions"]
                        + svg["polygonTextCollisions"]
                    )
                ]
                self.assertTrue(all(
                    collision["collisionKind"] == "stroke-text"
                    for svg in metrics["svgs"]
                    for collision in svg["linePathTextCollisions"]
                ))
                self.assertFalse(any(collision["textExcerpt"] == "SAFE"
                                     for collision in all_geometry_collisions))
                self.assertFalse(any(collision["textExcerpt"] == "R"
                                     for collision in all_geometry_collisions))


if __name__ == "__main__":
    unittest.main()
