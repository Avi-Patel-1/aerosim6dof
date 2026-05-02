import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { TelemetryRow } from "../types";

type ReplaySceneProps = {
  rows: TelemetryRow[];
  currentIndex: number;
  environmentMode: "range" | "coast" | "night";
  cameraMode: "chase" | "orbit" | "cockpit" | "map" | "rangeSafety";
  showTrail: boolean;
  showAxes: boolean;
  showWind: boolean;
  showVelocity?: boolean;
  showAcceleration?: boolean;
  showSensors?: boolean;
  trailColorMode?: "plain" | "speed" | "qbar" | "load" | "altitude";
  compact?: boolean;
};

type SceneState = {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  aircraft: THREE.Group;
  pathLine: THREE.Line;
  trailLine: THREE.Line;
  targetObject: THREE.Group;
  targetLine: THREE.Line;
  targetLabel: THREE.Sprite;
  interceptorObject: THREE.Group;
  interceptorLine: THREE.Line;
  interceptorLabel: THREE.Sprite;
  missMarker: THREE.Mesh;
  missLabel: THREE.Sprite;
  terrainLine: THREE.Line;
  altitudeLine: THREE.Line;
  velocityArrow: THREE.ArrowHelper;
  accelerationArrow: THREE.ArrowHelper;
  radarCone: THREE.Mesh;
  impactMarker: THREE.Mesh;
  axes: THREE.AxesHelper;
  windArrow: THREE.ArrowHelper;
  marker: THREE.Mesh;
  frame: number;
  clock: THREE.Clock;
};

const GROUND_Y = -10.28;

function disposeScene(scene: THREE.Scene) {
  scene.traverse((object) => {
    const mesh = object as THREE.Object3D & {
      geometry?: THREE.BufferGeometry;
      material?: THREE.Material | THREE.Material[];
    };
    if (Array.isArray(mesh.material)) {
      mesh.material.forEach((material) => {
        (material as THREE.Material & { map?: THREE.Texture | null }).map?.dispose();
        material.dispose();
      });
    } else {
      (mesh.material as THREE.Material & { map?: THREE.Texture | null } | undefined)?.map?.dispose();
      mesh.material?.dispose();
    }
    mesh.geometry?.dispose();
  });
}

function numberValue(row: TelemetryRow | undefined, key: string): number {
  const value = row?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function optionalNumber(row: TelemetryRow | undefined, key: string): number | null {
  const value = row?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringValue(row: TelemetryRow | undefined, key: string): string {
  const value = row?.[key];
  return typeof value === "string" ? value : "";
}

function circlePoints(radius: number, y: number, segments = 128): THREE.Vector3[] {
  return Array.from({ length: segments + 1 }, (_, index) => {
    const angle = (index / segments) * Math.PI * 2;
    return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
  });
}

function ridgePoints(z: number, yBase: number, height: number): THREE.Vector3[] {
  return Array.from({ length: 86 }, (_, index) => {
    const t = index / 85;
    const x = -108 + t * 216;
    const y = yBase + Math.sin(t * Math.PI * 5.5) * height + Math.sin(t * Math.PI * 17) * height * 0.28;
    return new THREE.Vector3(x, y, z + Math.sin(t * Math.PI * 3) * 3);
  });
}

function buildAircraft(): THREE.Group {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.45, 0.72, 4.8, 18),
    new THREE.MeshStandardMaterial({ color: "#ededf3", metalness: 0.28, roughness: 0.38 })
  );
  body.rotation.z = Math.PI / 2;
  const nose = new THREE.Mesh(
    new THREE.ConeGeometry(0.72, 1.55, 18),
    new THREE.MeshStandardMaterial({ color: "#cdddff", metalness: 0.12, roughness: 0.42 })
  );
  nose.rotation.z = -Math.PI / 2;
  nose.position.x = 3.15;
  const wing = new THREE.Mesh(
    new THREE.BoxGeometry(2.4, 0.12, 6.4),
    new THREE.MeshStandardMaterial({ color: "#c3c3cc", metalness: 0.18, roughness: 0.44 })
  );
  wing.position.x = 0.25;
  const tail = new THREE.Mesh(
    new THREE.BoxGeometry(1.2, 1.35, 0.16),
    new THREE.MeshStandardMaterial({ color: "#70707d", metalness: 0.1, roughness: 0.5 })
  );
  tail.position.x = -2.45;
  tail.position.y = 0.56;
  const cockpit = new THREE.Mesh(
    new THREE.BoxGeometry(0.78, 0.18, 1.2),
    new THREE.MeshStandardMaterial({ color: "#111119", metalness: 0.05, roughness: 0.3 })
  );
  cockpit.position.set(1.45, 0.48, 0);
  group.add(body, nose, wing, tail, cockpit);
  group.scale.setScalar(1.32);
  return group;
}

function buildTargetObject(): THREE.Group {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.OctahedronGeometry(1.6, 0),
    new THREE.MeshStandardMaterial({ color: "#ededf3", emissive: "#5d6cf0", emissiveIntensity: 0.18, roughness: 0.35 })
  );
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(3.2, 0.045, 8, 48),
    new THREE.MeshBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.84 })
  );
  ring.rotation.x = Math.PI / 2;
  const vertical = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -4.4, 0), new THREE.Vector3(0, 4.4, 0)]),
    new THREE.LineBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.58 })
  );
  const horizontal = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-4.4, 0, 0), new THREE.Vector3(4.4, 0, 0)]),
    new THREE.LineBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.58 })
  );
  group.add(body, ring, vertical, horizontal);
  group.visible = false;
  return group;
}

function buildInterceptorObject(): THREE.Group {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.ConeGeometry(0.8, 3.4, 18),
    new THREE.MeshStandardMaterial({ color: "#ffffff", metalness: 0.18, roughness: 0.32 })
  );
  body.rotation.z = -Math.PI / 2;
  const fins = new THREE.Mesh(
    new THREE.BoxGeometry(1.1, 0.12, 2.4),
    new THREE.MeshStandardMaterial({ color: "#9aa0b8", roughness: 0.44 })
  );
  fins.position.x = -0.8;
  group.add(body, fins);
  group.visible = false;
  return group;
}

function buildRadarCone(): THREE.Mesh {
  const cone = new THREE.Mesh(
    new THREE.ConeGeometry(4.5, 16, 28, 1, true),
    new THREE.MeshBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.12, wireframe: true })
  );
  cone.visible = false;
  return cone;
}

function buildTextSprite(text: string): THREE.Sprite {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthTest: false, depthWrite: false }));
  sprite.scale.set(22, 5.5, 1);
  sprite.visible = false;
  setSpriteText(sprite, text);
  return sprite;
}

function setSpriteText(sprite: THREE.Sprite, text: string) {
  const clean = text.trim();
  if (sprite.userData.label === clean) {
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "rgba(17, 17, 25, 0.78)";
  context.strokeStyle = "rgba(237, 237, 243, 0.46)";
  context.lineWidth = 2;
  roundRect(context, 10, 24, 492, 78, 14);
  context.fill();
  context.stroke();
  context.fillStyle = "#ededf3";
  context.font = "600 30px Arial, sans-serif";
  context.textBaseline = "middle";
  context.fillText(clean.slice(0, 28), 30, 63);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = sprite.material as THREE.SpriteMaterial;
  material.map?.dispose();
  material.map = texture;
  material.needsUpdate = true;
  sprite.userData.label = clean;
}

function roundRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function buildEnvironment(mode: ReplaySceneProps["environmentMode"]): THREE.Group {
  const group = new THREE.Group();
  const palettes = {
    range: { ground: "#1b1b26", wire: "#343444", runway: "#c3c3cc", accent: "#ededf3" },
    coast: { ground: "#171721", wire: "#313342", runway: "#c3c3cc", accent: "#cdddff" },
    night: { ground: "#111119", wire: "#272735", runway: "#ededf3", accent: "#ededf3" }
  };
  const palette = palettes[mode];
  const terrainGeometry = new THREE.PlaneGeometry(190, 190, 42, 42);
  const positions = terrainGeometry.attributes.position;
  for (let index = 0; index < positions.count; index += 1) {
    const x = positions.getX(index);
    const y = positions.getY(index);
    const ripple = mode === "coast" ? Math.sin(x * 0.05) * 0.8 : Math.sin(x * 0.07) * Math.cos(y * 0.05) * 1.4;
    positions.setZ(index, ripple);
  }
  terrainGeometry.computeVertexNormals();
  const terrain = new THREE.Mesh(
    terrainGeometry,
    new THREE.MeshStandardMaterial({ color: palette.ground, metalness: 0.02, roughness: 0.92 })
  );
  terrain.rotation.x = -Math.PI / 2;
  terrain.position.y = -12.85;
  const grid = new THREE.GridHelper(190, 34, palette.wire, palette.wire);
  grid.position.y = -11.72;
  const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material];
  gridMaterials.forEach((material) => {
    material.transparent = true;
    material.opacity = mode === "night" ? 0.2 : 0.14;
    material.depthWrite = false;
  });
  const runway = new THREE.Mesh(
    new THREE.BoxGeometry(92, 0.08, 6.5),
    new THREE.MeshStandardMaterial({ color: palette.runway, roughness: 0.5 })
  );
  runway.position.set(2, -11.44, 0);
  runway.rotation.y = -0.05;
  const centerLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-47, -11.32, 0), new THREE.Vector3(52, -11.32, 0)]),
    new THREE.LineDashedMaterial({ color: "#171721", dashSize: 3, gapSize: 2, transparent: true, opacity: 0.72 })
  );
  centerLine.computeLineDistances();
  const rangeRings = [34, 68, 102].map(
    (radius) =>
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(circlePoints(radius, -11.24)),
        new THREE.LineBasicMaterial({ color: palette.accent, transparent: true, opacity: mode === "night" ? 0.18 : 0.1 })
      )
  );
  const approachFan = new THREE.Group();
  [-1, 1].forEach((side) => {
    approachFan.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-46, -11.27, side * 3.25), new THREE.Vector3(76, -11.18, side * 22)]),
        new THREE.LineBasicMaterial({ color: palette.accent, transparent: true, opacity: 0.16 })
      )
    );
  });
  const ridgeBack = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ridgePoints(-104, 8, 2.8)),
    new THREE.LineBasicMaterial({ color: palette.accent, transparent: true, opacity: mode === "night" ? 0.24 : 0.16 })
  );
  const ridgeFront = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ridgePoints(-82, 1.5, 4.2)),
    new THREE.LineBasicMaterial({ color: palette.accent, transparent: true, opacity: mode === "night" ? 0.22 : 0.13 })
  );
  const horizon = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(
      Array.from({ length: 96 }, (_, index) => {
        const angle = (index / 95) * Math.PI * 2;
        return new THREE.Vector3(Math.cos(angle) * 120, 9 + Math.sin(angle * 3) * 3, Math.sin(angle) * 120);
      })
    ),
    new THREE.LineBasicMaterial({ color: palette.accent, transparent: true, opacity: mode === "night" ? 0.42 : 0.24 })
  );
  group.add(terrain, grid, runway, centerLine, approachFan, ridgeBack, ridgeFront, horizon, ...rangeRings);
  const runwayLights = new THREE.InstancedMesh(
    new THREE.BoxGeometry(0.28, 0.18, 0.28),
      new THREE.MeshStandardMaterial({ color: "#ededf3", emissive: "#ededf3", emissiveIntensity: mode === "night" ? 1.15 : 0.28 }),
    42
  );
  const matrix = new THREE.Matrix4();
  for (let index = 0; index < 21; index += 1) {
    const x = -45 + index * 4.5;
    matrix.makeTranslation(x, -11.17, -3.55);
    runwayLights.setMatrixAt(index * 2, matrix);
    matrix.makeTranslation(x, -11.17, 3.55);
    runwayLights.setMatrixAt(index * 2 + 1, matrix);
  }
  group.add(runwayLights);
  if (mode === "coast") {
    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(190, 82),
      new THREE.MeshStandardMaterial({ color: "#151725", metalness: 0.02, roughness: 0.65, transparent: true, opacity: 0.72 })
    );
    water.rotation.x = -Math.PI / 2;
    water.position.set(0, -11.36, -55);
    group.add(water);
  }
  if (mode === "night") {
    const stars = new THREE.BufferGeometry();
    const starPoints = Array.from({ length: 180 }, (_, index) => {
      const angle = index * 2.399;
      const radius = 78 + (index % 37) * 1.8;
      return new THREE.Vector3(Math.cos(angle) * radius, 28 + (index % 19), Math.sin(angle) * radius);
    });
    stars.setFromPoints(starPoints);
    group.add(new THREE.Points(stars, new THREE.PointsMaterial({ color: "#ededf3", size: 0.9, sizeAttenuation: true })));
  }
  return group;
}

function transformRows(rows: TelemetryRow[]) {
  const points = rows.map((row) => ({
    x: numberValue(row, "x_m"),
    y: numberValue(row, "y_m"),
    z: numberValue(row, "altitude_m")
  }));
  const rawTargetPoints = rows.map((row) => {
    const x = optionalNumber(row, "target_x_m");
    const y = optionalNumber(row, "target_y_m");
    const z = optionalNumber(row, "target_z_m");
    return x === null || y === null || z === null ? null : { x, y, z };
  });
  const rawInterceptorPoints = rows.map((row) => {
    const x = optionalNumber(row, "interceptor_x_m");
    const y = optionalNumber(row, "interceptor_y_m");
    const z = optionalNumber(row, "interceptor_z_m");
    return x === null || y === null || z === null ? null : { x, y, z };
  });
  const rawTerrainPoints = rows.map((row) => ({
    x: numberValue(row, "x_m"),
    y: numberValue(row, "y_m"),
    z: numberValue(row, "terrain_elevation_m")
  }));
  if (!points.length) {
    return {
      points: [new THREE.Vector3(0, 0, 0)],
      targetPoints: [null],
      interceptorPoints: [null],
      terrainPoints: [new THREE.Vector3(0, GROUND_Y, 0)],
      scale: 1,
      center: new THREE.Vector3(0, 0, 0)
    };
  }
  const extents = [
    ...points,
    ...rawTerrainPoints,
    ...rawTargetPoints.filter((point): point is { x: number; y: number; z: number } => point !== null),
    ...rawInterceptorPoints.filter((point): point is { x: number; y: number; z: number } => point !== null)
  ];
  const xs = extents.map((point) => point.x);
  const ys = extents.map((point) => point.y);
  const altitudes = extents.map((point) => Math.max(0, point.z));
  const centerX = (Math.min(...xs) + Math.max(...xs)) * 0.5;
  const centerY = (Math.min(...ys) + Math.max(...ys)) * 0.5;
  const maxAltitude = Math.max(...altitudes, 1);
  const extent = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), maxAltitude, 1);
  const scale = 105 / extent;
  return {
    points: points.map((point) => new THREE.Vector3((point.x - centerX) * scale, GROUND_Y + Math.max(0, point.z) * scale, -(point.y - centerY) * scale)),
    targetPoints: rawTargetPoints.map((point) =>
      point === null ? null : new THREE.Vector3((point.x - centerX) * scale, GROUND_Y + Math.max(0, point.z) * scale, -(point.y - centerY) * scale)
    ),
    interceptorPoints: rawInterceptorPoints.map((point) =>
      point === null ? null : new THREE.Vector3((point.x - centerX) * scale, GROUND_Y + Math.max(0, point.z) * scale, -(point.y - centerY) * scale)
    ),
    terrainPoints: rawTerrainPoints.map((point) => new THREE.Vector3((point.x - centerX) * scale, GROUND_Y + Math.max(0, point.z) * scale, -(point.y - centerY) * scale)),
    scale,
    center: new THREE.Vector3(centerX, 0, centerY)
  };
}

function metricColor(value: number, min: number, max: number): THREE.Color {
  const ratio = max > min ? THREE.MathUtils.clamp((value - min) / (max - min), 0, 1) : 0;
  return new THREE.Color().lerpColors(new THREE.Color("#70707d"), new THREE.Color("#ededf3"), ratio);
}

function coloredGeometry(points: THREE.Vector3[], rows: TelemetryRow[], mode: ReplaySceneProps["trailColorMode"]): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  if (!mode || mode === "plain" || points.length !== rows.length) {
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(points.flatMap(() => [0.93, 0.93, 0.95]), 3));
    return geometry;
  }
  const key = mode === "speed" ? "speed_mps" : mode === "qbar" ? "qbar_pa" : mode === "load" ? "load_factor_g" : "altitude_m";
  const values = rows.map((row) => numberValue(row, key));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const colors = values.flatMap((value) => {
    const color = metricColor(value, min, max);
    return [color.r, color.g, color.b];
  });
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  return geometry;
}

export function ReplayScene({
  rows,
  currentIndex,
  environmentMode,
  cameraMode,
  showTrail,
  showAxes,
  showWind,
  showVelocity = true,
  showAcceleration = false,
  showSensors = false,
  trailColorMode = "plain",
  compact = false
}: ReplaySceneProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<SceneState | null>(null);
  const transformed = useMemo(() => transformRows(rows), [rows]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(environmentMode === "night" ? "#08080d" : "#171721", 1);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(environmentMode === "night" ? "#08080d" : "#171721", 88, 282);
    const camera = new THREE.PerspectiveCamera(compact ? 52 : 44, 1, 0.1, 1000);
    camera.position.set(compact ? 58 : 76, compact ? 34 : 48, compact ? 70 : 88);
    camera.lookAt(0, 12, 0);
    const ambient = new THREE.AmbientLight("#cdd8e0", 0.6);
    const key = new THREE.DirectionalLight("#ffffff", 1.8);
    key.position.set(30, 70, 40);
    const fill = new THREE.DirectionalLight("#cdddff", 0.55);
    fill.position.set(-40, 25, -50);
    const landscape = buildEnvironment(environmentMode);
    const aircraft = buildAircraft();
    const pathLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: "#70707d", transparent: true, opacity: 0.32 })
    );
    const trailLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: "#ededf3", vertexColors: true, transparent: true, opacity: 0.9, linewidth: 2 })
    );
    const targetObject = buildTargetObject();
    const targetLabel = buildTextSprite("TARGET");
    const targetLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.5 })
    );
    targetLine.visible = false;
    const interceptorObject = buildInterceptorObject();
    const interceptorLabel = buildTextSprite("INTERCEPTOR");
    const interceptorLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: "#ededf3", transparent: true, opacity: 0.42 })
    );
    interceptorLine.visible = false;
    const missMarker = new THREE.Mesh(
      new THREE.TorusGeometry(2.2, 0.08, 8, 36),
      new THREE.MeshBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.72 })
    );
    missMarker.rotation.x = Math.PI / 2;
    missMarker.visible = false;
    const missLabel = buildTextSprite("MISS --");
    const terrainLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: "#cdddff", transparent: true, opacity: 0.34 })
    );
    const altitudeLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: "#ededf3", transparent: true, opacity: 0.32 })
    );
    const velocityArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 12, "#cdddff", 2.8, 1.4);
    const accelerationArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 10, "#ededf3", 2.4, 1.2);
    const radarCone = buildRadarCone();
    const impactMarker = new THREE.Mesh(
      new THREE.TorusGeometry(4.8, 0.12, 8, 48),
      new THREE.MeshBasicMaterial({ color: "#ededf3", transparent: true, opacity: 0.76 })
    );
    impactMarker.rotation.x = Math.PI / 2;
    impactMarker.visible = false;
    const axes = new THREE.AxesHelper(6);
    const windArrow = new THREE.ArrowHelper(
      new THREE.Vector3(1, 0, 0),
      new THREE.Vector3(-42, 26, -42),
      18,
      "#ededf3",
      3.2,
      1.5
    );
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 18, 18),
      new THREE.MeshStandardMaterial({ color: "#cdddff", emissive: "#272735", roughness: 0.35 })
    );
    aircraft.add(axes);
    scene.add(
      ambient,
      key,
      fill,
      landscape,
      terrainLine,
      pathLine,
      trailLine,
      targetLine,
      targetObject,
      targetLabel,
      interceptorLine,
      interceptorObject,
      interceptorLabel,
      missMarker,
      missLabel,
      altitudeLine,
      velocityArrow,
      accelerationArrow,
      radarCone,
      impactMarker,
      marker,
      windArrow,
      aircraft
    );
    const clock = new THREE.Clock();

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(rect.width, 1);
      const height = Math.max(rect.height, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const animate = () => {
      stateRef.current!.frame = window.requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    window.addEventListener("resize", resize);
    stateRef.current = {
      renderer,
      scene,
      camera,
      aircraft,
      pathLine,
      trailLine,
      targetObject,
      targetLine,
      targetLabel,
      interceptorObject,
      interceptorLine,
      interceptorLabel,
      missMarker,
      missLabel,
      terrainLine,
      altitudeLine,
      velocityArrow,
      accelerationArrow,
      radarCone,
      impactMarker,
      axes,
      windArrow,
      marker,
      frame: 0,
      clock
    };
    resize();
    animate();
    return () => {
      window.removeEventListener("resize", resize);
      window.cancelAnimationFrame(stateRef.current?.frame ?? 0);
      disposeScene(scene);
      renderer.dispose();
      stateRef.current = null;
    };
  }, [compact, environmentMode]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) {
      return;
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(transformed.points);
    state.pathLine.geometry.dispose();
    state.pathLine.geometry = geometry;
    const trailGeometry = coloredGeometry(transformed.points.slice(0, 1), rows.slice(0, 1), trailColorMode);
    state.trailLine.geometry.dispose();
    state.trailLine.geometry = trailGeometry;
    state.terrainLine.geometry.dispose();
    state.terrainLine.geometry = new THREE.BufferGeometry().setFromPoints(transformed.terrainPoints);
  }, [rows, trailColorMode, transformed]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) {
      return;
    }
    const index = Math.min(Math.max(currentIndex, 0), Math.max(transformed.points.length - 1, 0));
    const position = transformed.points[index] ?? new THREE.Vector3(0, 0, 0);
    const targetPosition = transformed.targetPoints[index];
    const interceptorPosition = transformed.interceptorPoints[index];
    const terrainPosition = transformed.terrainPoints[index] ?? new THREE.Vector3(position.x, GROUND_Y, position.z);
    const row = rows[index];
    state.aircraft.position.copy(position);
    state.marker.position.copy(position);
    const hasTarget = targetPosition instanceof THREE.Vector3;
    state.targetObject.visible = hasTarget;
    state.targetLine.visible = hasTarget;
    state.targetLabel.visible = hasTarget && !compact;
    if (hasTarget) {
      state.targetObject.position.copy(targetPosition);
      state.targetObject.rotation.y += 0.04;
      state.targetLabel.position.copy(targetPosition).add(new THREE.Vector3(0, 7.5, 0));
      const role = stringValue(row, "target_role");
      const label = stringValue(row, "target_label") || stringValue(row, "target_id") || "Target";
      setSpriteText(state.targetLabel, `${label}${role ? ` / ${role}` : ""}`);
      state.targetLine.geometry.dispose();
      state.targetLine.geometry = new THREE.BufferGeometry().setFromPoints([position, targetPosition]);
    }
    const hasInterceptor = interceptorPosition instanceof THREE.Vector3 && numberValue(row, "interceptor_launched") > 0.5;
    state.interceptorObject.visible = hasInterceptor;
    state.interceptorLine.visible = hasInterceptor && hasTarget;
    state.interceptorLabel.visible = hasInterceptor && !compact;
    state.missMarker.visible = hasInterceptor && hasTarget;
    state.missLabel.visible = hasInterceptor && hasTarget && !compact;
    if (hasInterceptor) {
      state.interceptorObject.position.copy(interceptorPosition);
      state.interceptorObject.lookAt(hasTarget ? targetPosition : position);
      state.interceptorLabel.position.copy(interceptorPosition).add(new THREE.Vector3(0, 6.5, 0));
      setSpriteText(state.interceptorLabel, stringValue(row, "interceptor_id") || "Interceptor");
      if (hasTarget) {
        state.interceptorLine.geometry.dispose();
        state.interceptorLine.geometry = new THREE.BufferGeometry().setFromPoints([interceptorPosition, targetPosition]);
        const midpoint = new THREE.Vector3().addVectors(interceptorPosition, targetPosition).multiplyScalar(0.5);
        state.missMarker.position.copy(midpoint);
        state.missLabel.position.copy(midpoint).add(new THREE.Vector3(0, 5.5, 0));
        const range = optionalNumber(row, "interceptor_range_m");
        const bestMiss = optionalNumber(row, "interceptor_best_miss_m");
        setSpriteText(state.missLabel, `range ${range === null ? "--" : range.toFixed(1)} m / best ${bestMiss === null ? "--" : bestMiss.toFixed(1)} m`);
      }
    }
    state.altitudeLine.visible = !compact;
    state.altitudeLine.geometry.dispose();
    state.altitudeLine.geometry = new THREE.BufferGeometry().setFromPoints([terrainPosition, position]);
    state.pathLine.visible = showTrail;
    state.trailLine.visible = showTrail;
    state.axes.visible = showAxes;
    const wind = new THREE.Vector3(numberValue(row, "wind_x_mps"), numberValue(row, "wind_z_mps"), -numberValue(row, "wind_y_mps"));
    const windMagnitude = wind.length();
    state.windArrow.visible = showWind && windMagnitude > 0.01;
    if (state.windArrow.visible) {
      state.windArrow.position.copy(position).add(new THREE.Vector3(0, 16, 0));
      state.windArrow.setDirection(wind.normalize());
      state.windArrow.setLength(Math.max(6, Math.min(18, windMagnitude * 1.7)), 3.2, 1.5);
    }
    const velocity = new THREE.Vector3(numberValue(row, "vx_mps"), numberValue(row, "vz_mps"), -numberValue(row, "vy_mps"));
    const velocityMagnitude = velocity.length();
    state.velocityArrow.visible = showVelocity && velocityMagnitude > 0.01;
    if (state.velocityArrow.visible) {
      state.velocityArrow.position.copy(position).add(new THREE.Vector3(0, 6, 0));
      state.velocityArrow.setDirection(velocity.normalize());
      state.velocityArrow.setLength(Math.max(8, Math.min(34, velocityMagnitude * 0.22)), 3.1, 1.4);
    }
    const previousVelocity = rows[Math.max(index - 1, 0)];
    const time = numberValue(row, "time_s");
    const previousTime = numberValue(previousVelocity, "time_s");
    const dt = Math.max(time - previousTime, 1e-3);
    const acceleration = new THREE.Vector3(
      (numberValue(row, "vx_mps") - numberValue(previousVelocity, "vx_mps")) / dt,
      (numberValue(row, "vz_mps") - numberValue(previousVelocity, "vz_mps")) / dt,
      -(numberValue(row, "vy_mps") - numberValue(previousVelocity, "vy_mps")) / dt
    );
    const accelerationMagnitude = acceleration.length();
    state.accelerationArrow.visible = showAcceleration && accelerationMagnitude > 0.01 && index > 0;
    if (state.accelerationArrow.visible) {
      state.accelerationArrow.position.copy(position).add(new THREE.Vector3(0, 9, 0));
      state.accelerationArrow.setDirection(acceleration.normalize());
      state.accelerationArrow.setLength(Math.max(6, Math.min(24, accelerationMagnitude * 2.4)), 2.5, 1.2);
    }
    state.radarCone.visible = showSensors && numberValue(row, "radar_valid") > 0.5;
    if (state.radarCone.visible) {
      state.radarCone.position.copy(position).add(new THREE.Vector3(0, -8, 0));
      state.radarCone.rotation.set(Math.PI, 0, 0);
    }
    state.impactMarker.visible = numberValue(row, "ground_contact") > 0.5;
    if (state.impactMarker.visible) {
      state.impactMarker.position.copy(terrainPosition).add(new THREE.Vector3(0, 0.08, 0));
    }
    if (showTrail) {
      const trailGeometry = coloredGeometry(transformed.points.slice(0, index + 1), rows.slice(0, index + 1), trailColorMode);
      state.trailLine.geometry.dispose();
      state.trailLine.geometry = trailGeometry;
    }
    const roll = THREE.MathUtils.degToRad(numberValue(row, "roll_deg"));
    const pitch = THREE.MathUtils.degToRad(numberValue(row, "pitch_deg"));
    const yaw = THREE.MathUtils.degToRad(numberValue(row, "yaw_deg"));
    state.aircraft.rotation.set(pitch, -yaw, roll, "XYZ");
    const previous = transformed.points[Math.max(index - 1, 0)] ?? position;
    const next = transformed.points[Math.min(index + 1, transformed.points.length - 1)] ?? position;
    const direction = new THREE.Vector3().subVectors(next, previous);
    if (direction.lengthSq() < 0.001) {
      direction.set(1, 0, 0);
    }
    direction.normalize();
    const right = new THREE.Vector3(-direction.z, 0, direction.x).normalize();
    const elapsed = state.clock.getElapsedTime();
    const target = new THREE.Vector3(position.x, position.y + 4, position.z);
    const desired = new THREE.Vector3();
    if (cameraMode === "cockpit") {
      desired.copy(position).addScaledVector(direction, 5.5).add(new THREE.Vector3(0, 2.2, 0));
      target.copy(position).addScaledVector(direction, 42).add(new THREE.Vector3(0, 4, 0));
    } else if (cameraMode === "map") {
      desired.set(position.x, position.y + 118, position.z + 0.1);
      target.copy(position);
    } else if (cameraMode === "rangeSafety") {
      desired.set(position.x - 108, position.y + 56, position.z + 112);
      target.copy(hasTarget ? targetPosition : position);
    } else if (cameraMode === "orbit") {
      const angle = elapsed * 0.18 + index * 0.01;
      desired.set(position.x + Math.cos(angle) * 62, position.y + 36, position.z + Math.sin(angle) * 62);
    } else {
      desired.copy(position).addScaledVector(direction, compact ? -30 : -42).addScaledVector(right, compact ? 5 : 9).add(new THREE.Vector3(0, compact ? 13 : 20, 0));
    }
    state.camera.position.lerp(desired, cameraMode === "cockpit" ? 0.34 : 0.18);
    state.camera.lookAt(target);
  }, [cameraMode, compact, currentIndex, rows, showAcceleration, showAxes, showSensors, showTrail, showVelocity, showWind, trailColorMode, transformed]);

  return <canvas ref={canvasRef} className={compact ? "replay-canvas compact-preview" : "replay-canvas"} aria-label="3D replay scene" />;
}
