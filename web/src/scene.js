(function () {
  "use strict";
  const T = THREE;
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- palette ----
  const C = {
    cyan: 0x4ec9e0, cyanDim: 0x1f5666, orange: 0xff8c42, green: 0x5fd08a,
    amber: 0xe0a458, wall: 0x0c1420, floor: 0x0a1018, iron: 0x37506a,
    glass: 0x123044, bg: 0x05080e,
  };

  // ---- renderer / scene / camera ----
  const host = document.getElementById("scene");
  const renderer = new T.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.setClearColor(C.bg, 1);
  host.appendChild(renderer.domElement);

  const scene = new T.Scene();
  scene.fog = new T.FogExp2(C.bg, 0.012);

  const camera = new T.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 400);

  // ---- lighting ----
  scene.add(new T.HemisphereLight(0x3d5c78, 0x0a1018, 0.9));
  const amb = new T.AmbientLight(0x2a3d50, 0.8); scene.add(amb);
  function glow(color, intensity, dist, x, y, z) {
    const l = new T.PointLight(color, intensity, dist, 2);
    l.position.set(x, y, z); scene.add(l); return l;
  }

  // ---- shared materials ----
  const matWall = new T.MeshStandardMaterial({ color: C.wall, roughness: 0.95, metalness: 0.05 });
  const matIron = new T.MeshStandardMaterial({ color: C.iron, roughness: 0.6, metalness: 0.4 });
  const edgeMat = new T.LineBasicMaterial({ color: C.cyan, transparent: true, opacity: 0.5 });
  const edgeMatDim = new T.LineBasicMaterial({ color: C.cyanDim, transparent: true, opacity: 0.6 });

  // returns Group: dark solid + glowing wireframe edges
  function edged(geo, mat, eMat) {
    const g = new T.Group();
    g.add(new T.Mesh(geo, mat || matWall));
    g.add(new T.LineSegments(new T.EdgesGeometry(geo, 25), eMat || edgeMat));
    return g;
  }
  function box(w, h, d, mat, eMat) { return edged(new T.BoxGeometry(w, h, d), mat, eMat); }

  // ---- floor: slag-glass panels with a schematic grid ----
  function floorSlab(cx, cz, w, d, tint) {
    const m = new T.Mesh(new T.PlaneGeometry(w, d),
      new T.MeshStandardMaterial({ color: tint || C.floor, roughness: 0.85, metalness: 0.15 }));
    m.rotation.x = -Math.PI / 2; m.position.set(cx, 0, cz); scene.add(m);
    const grid = new T.GridHelper(Math.max(w, d), Math.round(Math.max(w, d) / 2), C.cyanDim, C.cyanDim);
    grid.material.transparent = true; grid.material.opacity = 0.22;
    grid.position.set(cx, 0.02, cz);
    // clip grid to slab via scale (GridHelper is square; acceptable overspill hidden by fog/walls)
    scene.add(grid);
  }

  // ---- iron U-channel rib (portal frame) ----
  function rib(cx, cz, w, h, mat) {
    const g = new T.Group();
    const t = 0.35;
    const top = box(w + t, t, t, mat || matIron, edgeMatDim); top.position.set(cx, h, cz); g.add(top);
    const lp = box(t, h, t, mat || matIron, edgeMatDim); lp.position.set(cx - w / 2, h / 2, cz); g.add(lp);
    const rp = box(t, h, t, mat || matIron, edgeMatDim); rp.position.set(cx + w / 2, h / 2, cz); g.add(rp);
    scene.add(g); return g;
  }

  // ---- doorway frame (U-channel, brighter) ----
  function doorway(cx, cz, facingZ, w, h) {
    const g = new T.Group();
    const t = 0.5;
    const dz = facingZ ? 0 : 0, dx = facingZ ? 0 : 0;
    const mat = matIron;
    const top = box(w, t, t, mat, edgeMat); top.position.set(cx, h, cz); g.add(top);
    const a = box(t, h, t, mat, edgeMat); a.position.set(cx - w / 2, h / 2, cz); g.add(a);
    const b = box(t, h, t, mat, edgeMat); b.position.set(cx + w / 2, h / 2, cz); g.add(b);
    scene.add(g); return g;
  }

  // ---- 3D schematic label (canvas sprite) ----
  function label(text, sub, color, x, y, z, scale) {
    const cv = document.createElement("canvas"); cv.width = 512; cv.height = 160;
    const x2 = cv.getContext("2d");
    x2.fillStyle = "rgba(8,14,22,0.72)"; x2.fillRect(0, 0, 512, 160);
    x2.strokeStyle = "#" + color.toString(16).padStart(6, "0"); x2.lineWidth = 3;
    x2.strokeRect(6, 6, 500, 148);
    x2.fillStyle = "#eaf6fb"; x2.font = "600 40px ui-monospace,Menlo,Consolas,monospace";
    x2.textBaseline = "top"; x2.fillText(text, 26, 30);
    if (sub) { x2.fillStyle = "#6f8595"; x2.font = "26px ui-monospace,Menlo,Consolas,monospace"; x2.fillText(sub, 26, 88); }
    const tex = new T.CanvasTexture(cv);
    const sp = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthTest: true }));
    sp.position.set(x, y, z); const s = scale || 1; sp.scale.set(6.4 * s, 2 * s, 1);
    scene.add(sp); return sp;
  }

  // ================= COLONY LAYOUT =================
  // Walkable regions (AABB on X/Z) + zone metadata for the HUD.
  const regions = [
    { id: "canopy", name: "SURFACE CANOPY · AIRLOCK", minX: -6, maxX: 6, minZ: -15, maxZ: -1,
      press: "3.0 kPa", grav: "0.00 g", depth: "0 m", seal: "mud-sealed origami" },
    { id: "backbone", name: "TUNNEL BACKBONE", minX: -4, maxX: 4, minZ: -1, maxZ: 92,
      press: "8.0 kPa", grav: "0.00 g", depth: "sloping to 30 m", seal: "slag-glass lined" },
    { id: "lab", name: "CLEAN LAB · ORIGINAL WORKSHOP", minX: -26, maxX: -4, minZ: 8, maxZ: 30,
      press: "8.0 kPa", grav: "0.05 g", depth: "8 m", seal: "pressurized dome" },
    { id: "bio", name: "BIO-CHAMBER · 200–500 L REACTORS", minX: 4, maxX: 26, minZ: 34, maxZ: 58,
      press: "5.0 kPa", grav: "0.10 g", depth: "14 m", seal: "sealed vat gallery" },
    { id: "carnival", name: "CARNIVAL CENTRIFUGE · HEAVY INDUSTRY", minX: -34, maxX: -4, minZ: 60, maxZ: 92,
      press: "6.0 kPa", grav: "0.10–0.20 g", depth: "22 m", seal: "local slag + iron" },
    { id: "face", name: "MINE FACE · ORE STOCKPILE", minX: -5, maxX: 5, minZ: 92, maxZ: 112,
      press: "8.0 kPa", grav: "0.00 g", depth: "30 m", seal: "raw rock · advancing" },
  ];
  function regionAt(x, z) {
    for (const r of regions) if (x >= r.minX && x <= r.maxX && z >= r.minZ && z <= r.maxZ) return r;
    return null;
  }

  const CH = 5.2; // corridor/ceiling height

  // ---- floors ----
  floorSlab(0, -8, 13, 15, 0x0d1622);           // canopy
  floorSlab(0, 45.5, 8, 94);                     // backbone
  floorSlab(-15, 19, 23, 23, 0x0b141d);          // lab
  floorSlab(15, 46, 23, 25, 0x0a1a16);           // bio
  floorSlab(-19, 76, 31, 33, 0x14110a);          // carnival
  floorSlab(0, 102, 10, 22, 0x0c0f14);           // mine face

  // ---- backbone side walls, split around the three doorways ----
  function wallRun(xside, segs) {
    for (const [z0, z1] of segs) {
      const len = z1 - z0;
      const w = box(0.4, CH, len, matWall, edgeMatDim);
      w.position.set(xside, CH / 2, (z0 + z1) / 2); scene.add(w);
    }
  }
  // left wall gap at lab (z 12..26) and carnival (z 64..88)
  wallRun(-4, [[-1, 12], [26, 64], [88, 92]]);
  // right wall gap at bio (z 38..54)
  wallRun(4, [[-1, 38], [54, 92]]);
  // backbone ceiling
  (function () { const c = box(8, 0.3, 93, matWall, edgeMatDim); c.position.set(0, CH, 45.5); scene.add(c); })();

  // ribs + rail + cabling down the backbone
  for (let z = 2; z <= 90; z += 6) rib(0, z, 8, CH, matIron);
  (function rail() {
    for (const rx of [-1.1, 1.1]) {
      const r = box(0.15, 0.12, 92, matIron, edgeMat); r.position.set(rx, 0.08, 45.5); scene.add(r);
    }
    for (let z = 0; z <= 92; z += 2.2) { const tie = box(2.6, 0.08, 0.18, matIron, edgeMatDim); tie.position.set(0, 0.05, z); scene.add(tie); }
  })();
  for (let z = 6; z <= 88; z += 22) glow(C.cyan, 0.85, 26, 0, CH - 0.6, z);

  // doorway frames at the junctions
  doorway(-4, 19, false, CH - 0.4, CH - 0.3);
  doorway(4, 46, false, CH - 0.4, CH - 0.3);
  doorway(-4, 76, false, CH + 0.6, CH - 0.3);

  // ================= CANOPY (entry dome) =================
  (function canopy() {
    const dome = new T.Mesh(
      new T.SphereGeometry(8.2, 22, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      new T.MeshStandardMaterial({ color: 0x101d2b, roughness: 1, metalness: 0, side: T.BackSide, transparent: true, opacity: 0.5 }));
    dome.position.set(0, 0, -8); scene.add(dome);
    scene.add(new T.LineSegments(new T.WireframeGeometry(dome.geometry),
      new T.LineBasicMaterial({ color: C.cyanDim, transparent: true, opacity: 0.35 })).translateZ(-8).translateY(0));
    glow(0x9fd8ff, 1.1, 30, 0, 6, -8);
    label("SURFACE CANOPY", "deployable origami · dust + micrometeorite shield", C.cyan, 0, 6.6, -8, 1.15);
  })();

  // ================= CLEAN LAB (0.05 g dome + EM press) =================
  (function lab() {
    const R = 11.5, cx = -15, cz = 19;
    const dome = new T.Mesh(
      new T.SphereGeometry(R, 26, 14, 0, Math.PI * 2, 0, Math.PI / 2),
      new T.MeshStandardMaterial({ color: 0x0f1c2a, roughness: 1, side: T.BackSide }));
    dome.position.set(cx, 0, cz); scene.add(dome);
    const wf = new T.LineSegments(new T.WireframeGeometry(dome.geometry),
      new T.LineBasicMaterial({ color: C.cyan, transparent: true, opacity: 0.16 }));
    wf.position.set(cx, 0, cz); scene.add(wf);
    glow(0xbfe6ff, 1.5, 32, cx, 8, cz);
    // workbenches
    for (const [bx, bz] of [[-21, 14], [-21, 24], [-9, 26]]) {
      const b = box(3.2, 1.0, 1.4, matWall, edgeMat); b.position.set(bx, 0.5, bz); scene.add(b);
      const p = box(0.1, 1.1, 0.1, matIron, edgeMat); p.position.set(bx, 1.6, bz); scene.add(p); // instrument post
    }
    // EM press: OPEN frame (posts + base) so the coils glow through
    const press = new T.Group();
    const base = box(3, 0.3, 3, matWall, edgeMat); base.position.set(-15, 0.15, 18); press.add(base);
    const cap = box(3, 0.25, 3, matWall, edgeMat); cap.position.set(-15, 3.3, 18); press.add(cap);
    for (const [ox, oz] of [[-1.35, -1.35], [1.35, -1.35], [-1.35, 1.35], [1.35, 1.35]]) {
      const post = box(0.16, 3.2, 0.16, matIron, edgeMat); post.position.set(-15 + ox, 1.7, 18 + oz); press.add(post);
    }
    for (let i = 0; i < 3; i++) {
      const coil = new T.Mesh(new T.TorusGeometry(1.05, 0.12, 8, 24),
        new T.MeshStandardMaterial({ color: C.orange, emissive: 0x7a3410, emissiveIntensity: 0.6, roughness: 0.4 }));
      coil.position.set(-15, 0.8 + i * 0.9, 18); coil.rotation.x = Math.PI / 2; press.add(coil);
    }
    scene.add(press);
    glow(C.orange, 1.1, 14, -15, 1.6, 18);
    label("CLEAN LAB", "original 0.05 g workshop · EM press · patterned deposition", C.cyan, cx, 8.4, cz, 1.1);
  })();

  // ================= BIO-CHAMBER (vats) =================
  const bioVats = [];
  (function bio() {
    const cx = 15, cz = 46;
    const ceil = box(23, 0.3, 25, matWall, edgeMatDim); ceil.position.set(cx, CH + 1, cz); scene.add(ceil);
    // back + side walls
    const bw = box(0.4, CH + 1, 25, matWall, edgeMatDim); bw.position.set(26, (CH + 1) / 2, cz); scene.add(bw);
    const nw = box(23, CH + 1, 0.4, matWall, edgeMatDim); nw.position.set(cx, (CH + 1) / 2, 58); scene.add(nw);
    const sw = box(23, CH + 1, 0.4, matWall, edgeMatDim); sw.position.set(cx, (CH + 1) / 2, 34); scene.add(sw);
    const vatMat = new T.MeshStandardMaterial({ color: C.green, emissive: 0x1c8a52, emissiveIntensity: 1.0,
      roughness: 0.25, metalness: 0.1, transparent: true, opacity: 0.82 });
    for (const [vx, vz, h] of [[11, 40, 3.4], [11, 50, 4.2], [18, 42, 3.0], [18, 52, 3.8], [23, 46, 4.6]]) {
      const vat = new T.Mesh(new T.CylinderGeometry(1.5, 1.5, h, 20), vatMat);
      vat.position.set(vx, h / 2, vz); scene.add(vat);
      scene.add(new T.LineSegments(new T.EdgesGeometry(vat.geometry), edgeMat).translateX(vx).translateY(h / 2).translateZ(vz));
      bioVats.push(vat);
    }
    glow(C.green, 1.9, 32, cx, 4, cz);
    label("BIO-CHAMBER", "bioleach reactors · 200–500 L · algae photobioreactor", C.green, cx, CH + 1.9, cz, 1.1);
  })();

  // ================= CARNIVAL CENTRIFUGE (rotating ring) =================
  let centrifuge = null;
  (function carnival() {
    const cx = -19, cz = 76;
    const ceil = box(31, 0.3, 33, matWall, edgeMatDim); ceil.position.set(cx, CH + 2.6, cz); scene.add(ceil);
    const bw = box(0.4, CH + 2.6, 33, matWall, edgeMatDim); bw.position.set(-34, (CH + 2.6) / 2, cz); scene.add(bw);
    const nw = box(31, CH + 2.6, 0.4, matWall, edgeMatDim); nw.position.set(cx, (CH + 2.6) / 2, 92); scene.add(nw);
    const sw = box(31, CH + 2.6, 0.4, matWall, edgeMatDim); sw.position.set(cx, (CH + 2.6) / 2, 60); scene.add(sw);
    // rotating ring + spokes + cabins
    centrifuge = new T.Group(); centrifuge.position.set(cx, 1.4, cz);
    const ring = new T.Mesh(new T.TorusGeometry(8.5, 0.35, 10, 40),
      new T.MeshStandardMaterial({ color: C.amber, emissive: 0x7a5410, emissiveIntensity: 0.9, roughness: 0.5, metalness: 0.4 }));
    ring.rotation.x = Math.PI / 2; centrifuge.add(ring);
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      const spoke = box(0.18, 0.18, 8.4, matIron, edgeMatDim);
      spoke.position.set(Math.cos(a) * 4.25, 0, Math.sin(a) * 4.25);
      spoke.rotation.y = -a; centrifuge.add(spoke);
    }
    for (let i = 0; i < 4; i++) {
      const a = (i / 4) * Math.PI * 2;
      const cab = box(1.6, 1.2, 1.2, matWall, edgeMat);
      cab.position.set(Math.cos(a) * 8.5, 0, Math.sin(a) * 8.5); centrifuge.add(cab);
    }
    const hub = new T.Mesh(new T.CylinderGeometry(0.6, 0.6, 1.6, 12), matIron); centrifuge.add(hub);
    scene.add(centrifuge);
    // support pylons
    for (const [px, pz] of [[-27, 68], [-11, 68], [-27, 84], [-11, 84]]) {
      const py = box(0.4, CH + 2, 0.4, matIron, edgeMatDim); py.position.set(px, (CH + 2) / 2, pz); scene.add(py);
    }
    glow(C.amber, 0.85, 30, cx, 6.5, cz);
    glow(C.amber, 0.5, 14, cx, 1.6, cz);
    label("CARNIVAL CENTRIFUGE", "locally-built · track-and-wheel · 0.1–0.2 g casting floor", C.amber, cx, CH + 3.6, cz, 1.15);
  })();

  // ================= MINE FACE =================
  (function face() {
    const cz = 104;
    const backWall = new T.Mesh(new T.PlaneGeometry(10, 8),
      new T.MeshStandardMaterial({ color: 0x14100a, roughness: 1 }));
    backWall.position.set(0, 3, 112); backWall.rotation.y = Math.PI; scene.add(backWall);
    // ore stockpiles (low-poly cobbles)
    for (let i = 0; i < 14; i++) {
      const s = 0.4 + Math.abs(Math.sin(i * 12.9)) * 0.9;
      const ore = new T.Mesh(new T.DodecahedronGeometry(s),
        new T.MeshStandardMaterial({ color: i % 3 ? 0x3a3026 : 0x4a3a26, roughness: 1, metalness: 0.2 }));
      ore.position.set(-3.4 + (i % 5) * 1.7, s * 0.6, 98 + Math.floor(i / 5) * 2.4);
      ore.rotation.set(i, i * 2, i * 3); scene.add(ore);
    }
    glow(C.orange, 1.2, 26, 0, 3, 108);
    label("MINE FACE", "advancing dig · rock = pressure vessel + shield", C.amber, 0, 5.4, 106, 1.0);
  })();

  // ================= ANTS =================
  function makeAnt(color) {
    const g = new T.Group();
    const bodyMat = new T.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, roughness: 0.5 });
    const thorax = new T.Mesh(new T.BoxGeometry(0.34, 0.2, 0.5), bodyMat); thorax.position.y = 0.28; g.add(thorax);
    const head = new T.Mesh(new T.BoxGeometry(0.24, 0.2, 0.22), bodyMat); head.position.set(0, 0.3, 0.36); g.add(head);
    const legMat = new T.MeshStandardMaterial({ color: 0x25333f, roughness: 0.8 });
    const legs = [];
    for (let s = -1; s <= 1; s += 2) for (let i = -1; i <= 1; i++) {
      const leg = new T.Mesh(new T.BoxGeometry(0.05, 0.05, 0.34), legMat);
      leg.position.set(s * 0.24, 0.14, i * 0.18); leg.rotation.z = s * 0.5; leg.rotation.x = 0.4; g.add(leg); legs.push(leg);
    }
    for (let s = -1; s <= 1; s += 2) {
      const man = new T.Mesh(new T.ConeGeometry(0.04, 0.2, 6), bodyMat);
      man.position.set(s * 0.08, 0.3, 0.5); man.rotation.x = Math.PI / 2; g.add(man);
    }
    g.userData.legs = legs;
    scene.add(g); return g;
  }
  // workers ride the backbone rail; a taskmaster loiters near the lab; a few in chambers
  const ants = [];
  function addAnt(color, path, speed, phase) {
    const a = makeAnt(color); a.userData.path = path; a.userData.speed = speed;
    a.userData.t = phase || Math.random(); ants.push(a); return a;
  }
  const backbonePath = (t) => new T.Vector3(Math.sin(t * Math.PI * 2) * 1.3, 0, 4 + ((t * 90) % 88));
  for (let i = 0; i < 5; i++) addAnt(C.orange, backbonePath, 0.02 + i * 0.004, i / 5);
  addAnt(C.cyan, (t) => new T.Vector3(-15 + Math.cos(t * 6.28) * 6, 0, 19 + Math.sin(t * 6.28) * 6), 0.05);
  addAnt(C.orange, (t) => new T.Vector3(15 + Math.cos(t * 6.28) * 7, 0, 46 + Math.sin(t * 6.28) * 8), 0.04);
  addAnt(C.orange, (t) => new T.Vector3(-19 + Math.cos(t * 6.28) * 11, 0, 76 + Math.sin(t * 6.28) * 12), 0.05);

  // ================= DUST MOTES =================
  (function dust() {
    const n = 260, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - 0.5) * 60; pos[i * 3 + 1] = Math.random() * 5; pos[i * 3 + 2] = Math.random() * 110 - 6; }
    const geo = new T.BufferGeometry(); geo.setAttribute("position", new T.Float32BufferAttribute(pos, 3));
    const pts = new T.Points(geo, new T.PointsMaterial({ color: C.cyan, size: 0.04, transparent: true, opacity: 0.5 }));
    scene.add(pts); scene.userData.dust = pts;
  })();

  // ================= CONTROLS (pointer-lock FPS) =================
  const state = { yaw: Math.PI, pitch: -0.05, keys: {}, locked: false, region: regions[0] };
  const pos = new T.Vector3(0, 1.7, -11);
  const startOverlay = document.getElementById("start");
  const enterBtn = document.getElementById("enter");
  const el = renderer.domElement;

  enterBtn.addEventListener("click", () => el.requestPointerLock());
  document.addEventListener("pointerlockchange", () => {
    state.locked = document.pointerLockElement === el;
    startOverlay.classList.toggle("gone", state.locked);
    document.querySelectorAll(".hud").forEach((h) => h.classList.toggle("live", state.locked));
    document.getElementById("cross").classList.toggle("live", state.locked);
  });
  document.addEventListener("mousemove", (e) => {
    if (!state.locked) return;
    state.yaw -= e.movementX * 0.0022;
    state.pitch -= e.movementY * 0.0022;
    state.pitch = Math.max(-1.35, Math.min(1.35, state.pitch));
  });
  addEventListener("keydown", (e) => { state.keys[e.code] = true; });
  addEventListener("keyup", (e) => { state.keys[e.code] = false; });
  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });

  // HUD elements
  const H = {
    name: document.getElementById("z-name"), press: document.getElementById("z-press"),
    grav: document.getElementById("z-grav"), depth: document.getElementById("z-depth"),
    seal: document.getElementById("z-seal"), head: document.getElementById("n-head"),
    x: document.getElementById("n-x"), z: document.getElementById("n-z"),
  };
  const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  function updateHUD() {
    const r = state.region;
    H.name.textContent = r.name; H.press.textContent = r.press;
    H.grav.textContent = r.grav; H.depth.textContent = r.depth; H.seal.textContent = r.seal;
    let deg = ((state.yaw * 180 / Math.PI) % 360 + 360) % 360;
    H.head.textContent = COMPASS[Math.round(deg / 45) % 8] + " " + deg.toFixed(0).padStart(3, "0") + "°";
    H.x.textContent = pos.x.toFixed(1); H.z.textContent = pos.z.toFixed(1);
  }

  // ================= LOOP =================
  const clock = new T.Clock();
  let bob = 0;
  function frame() {
    requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);

    // movement
    if (state.locked) {
      const run = state.keys.ShiftLeft || state.keys.ShiftRight ? 2.1 : 1;
      const speed = 6.0 * run * dt;
      let fwd = 0, str = 0;
      if (state.keys.KeyW || state.keys.ArrowUp) fwd += 1;
      if (state.keys.KeyS || state.keys.ArrowDown) fwd -= 1;
      if (state.keys.KeyD || state.keys.ArrowRight) str += 1;
      if (state.keys.KeyA || state.keys.ArrowLeft) str -= 1;
      const sinY = Math.sin(state.yaw), cosY = Math.cos(state.yaw);
      // forward is -Z when yaw 0
      let dx = (-sinY * fwd + cosY * str) * speed;
      let dz = (-cosY * fwd - sinY * str) * speed;
      const moving = fwd || str;
      // region-constrained motion with wall sliding
      let nx = pos.x + dx, nz = pos.z + dz;
      if (regionAt(nx, nz)) { pos.x = nx; pos.z = nz; }
      else if (regionAt(nx, pos.z)) { pos.x = nx; }
      else if (regionAt(pos.x, nz)) { pos.z = nz; }
      const cur = regionAt(pos.x, pos.z); if (cur) state.region = cur;
      if (moving && !REDUCED) bob += speed * 1.5;
    }
    const eye = 1.7 + (REDUCED ? 0 : Math.sin(bob) * 0.045);
    camera.position.set(pos.x, eye, pos.z);
    const dir = new T.Vector3(
      -Math.sin(state.yaw) * Math.cos(state.pitch),
      Math.sin(state.pitch),
      -Math.cos(state.yaw) * Math.cos(state.pitch)
    );
    camera.lookAt(camera.position.clone().add(dir));

    // animate ants
    const time = clock.elapsedTime;
    for (const a of ants) {
      a.userData.t = (a.userData.t + a.userData.speed * dt) % 1;
      const p = a.userData.path(a.userData.t);
      const p2 = a.userData.path((a.userData.t + 0.01) % 1);
      a.position.set(p.x, 0, p.z);
      a.lookAt(p2.x, 0, p2.z);
      if (!REDUCED) for (let i = 0; i < a.userData.legs.length; i++)
        a.userData.legs[i].rotation.x = 0.4 + Math.sin(time * 10 + i * 1.7) * 0.35;
    }
    // ambient motion
    if (!REDUCED) {
      if (centrifuge) centrifuge.rotation.y += dt * 0.25;
      const pulse = 0.85 + Math.sin(time * 1.3) * 0.25;
      for (const v of bioVats) v.material.emissiveIntensity = pulse;
      if (scene.userData.dust) scene.userData.dust.rotation.y += dt * 0.01;
    }

    updateHUD();
    renderer.render(scene, camera);
  }
  // seed HUD before entering
  updateHUD();
  frame();
})();
