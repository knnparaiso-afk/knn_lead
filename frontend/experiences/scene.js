import { Engine } from "@babylonjs/core/Engines/engine.js";
import { Scene } from "@babylonjs/core/scene.js";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera.js";
import { Camera } from "@babylonjs/core/Cameras/camera.js";
import { Vector3 } from "@babylonjs/core/Maths/math.vector.js";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color.js";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight.js";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight.js";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial.js";
import { DynamicTexture } from "@babylonjs/core/Materials/Textures/dynamicTexture.js";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode.js";
import { CreateBox } from "@babylonjs/core/Meshes/Builders/boxBuilder.js";
import { CreateGround } from "@babylonjs/core/Meshes/Builders/groundBuilder.js";
import { CreatePlane } from "@babylonjs/core/Meshes/Builders/planeBuilder.js";
import { SceneLoader } from "@babylonjs/core/Loading/sceneLoader.js";
import { PointerEventTypes } from "@babylonjs/core/Events/pointerEvents.js";
import { ShadowGenerator } from "@babylonjs/core/Lights/Shadows/shadowGenerator.js";
import "@babylonjs/core/Materials/standardMaterial.js";
import "@babylonjs/core/Bones/index.js";
import "@babylonjs/core/Animations/index.js";
import "@babylonjs/loaders/glTF/2.0/glTFLoader.js";
import assets from "./assets.json";

export async function createAdventure(canvas, onChoice) {
  const engine = new Engine(canvas, true, { stencil: false, powerPreference: "low-power" }, false);
  engine.setHardwareScalingLevel(Math.max(1, window.devicePixelRatio / 1.25));
  const scene = new Scene(engine);
  scene.clearColor = Color4.FromHexString("#D9E3CDFF");
  const camera = new ArcRotateCamera("camera", -Math.PI / 2.8, 1.12, 10, new Vector3(0, 1.1, 0), scene);
  camera.mode = Camera.ORTHOGRAPHIC_CAMERA;
  camera.minZ = .1;
  const hemi = new HemisphericLight("ambient", new Vector3(0, 1, 0), scene);
  hemi.intensity = .65;
  hemi.groundColor = Color3.FromHexString("#A8AA91");
  const sun = new DirectionalLight("sun", new Vector3(-.4, -1, .5), scene);
  sun.intensity = .8;
  sun.position = new Vector3(-3, 7, -5);
  const shadows = new ShadowGenerator(512, sun);
  shadows.usePoissonSampling = true;
  shadows.bias = .0005;
  shadows.normalBias = .02;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const containers = new Map(), rooms = new Map();
  let activeRoom, activeQuestion, generation = 0, disposed = false, reactionTimer;

  function resize() {
    engine.resize();
    const aspect = canvas.clientWidth / Math.max(1, canvas.clientHeight);
    const width = 4.2;
    camera.orthoLeft = -width;
    camera.orthoRight = width;
    camera.orthoTop = width / aspect;
    camera.orthoBottom = -width / aspect;
  }
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  resize();

  function material(name, color) {
    const result = new StandardMaterial(name, scene);
    result.diffuseColor = Color3.FromHexString(color);
    result.specularColor = Color3.Black();
    return result;
  }
  const palette = {
    cream: material("cream", "#F4E3C2"), green: material("green", "#25594F"),
    orange: material("orange", "#EB7548"), floor: material("floor", "#D0B793"),
    glass: material("glass", "#B9D9D4"), pale: material("pale", "#E5E9D8"),
  };
  function box(name, parent, size, position, mat) {
    const mesh = CreateBox(name, { width: size[0], height: size[1], depth: size[2] }, scene);
    mesh.parent = parent;
    mesh.position.set(...position);
    mesh.material = mat;
    mesh.isPickable = false;
    return mesh;
  }
  function sign(name, parent, lines, position, width = 2.4, height = .65) {
    const texture = new DynamicTexture(name + "-texture", { width: 768, height: 256 }, scene, false);
    const ctx = texture.getContext();
    ctx.fillStyle = "#254F47";
    ctx.fillRect(0, 0, 768, 256);
    ctx.fillStyle = "#FFF6DE";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = lines.length === 1 ? "bold 64px Arial" : "bold 44px Arial";
    lines.forEach((line, i) => ctx.fillText(line, 384, 128 + (i - (lines.length - 1) / 2) * 68));
    texture.update();
    const mat = new StandardMaterial(name + "-material", scene);
    mat.diffuseTexture = texture;
    mat.emissiveColor = new Color3(.3, .3, .3);
    mat.specularColor = Color3.Black();
    mat.backFaceCulling = false;
    const plane = CreatePlane(name, { width, height }, scene);
    plane.parent = parent;
    plane.position.set(...position);
    plane.material = mat;
    plane.isPickable = false;
    return plane;
  }
  async function load(key) {
    if (!containers.has(key)) {
      containers.set(key, SceneLoader.LoadAssetContainerAsync("", assets[key], scene));
    }
    return containers.get(key);
  }
  async function place(key, parent, position, height, rotation = 0, choice) {
    const container = await load(key);
    if (disposed) throw new Error("Cenário encerrado.");
    const instance = container.instantiateModelsToScene((name) => key + "-" + parent.name + "-" + name);
    const root = new TransformNode(key + "-root", scene);
    instance.rootNodes.forEach((node) => { node.parent = root; node.computeWorldMatrix(true); });
    const bounds = root.getHierarchyBoundingVectors(true);
    const scale = height / Math.max(.001, bounds.max.y - bounds.min.y);
    root.scaling.setAll(scale);
    root.position.set(position[0], position[1] - bounds.min.y * scale, position[2]);
    root.rotation.y = rotation;
    root.parent = parent;
    root.getChildMeshes().forEach((mesh) => {
      mesh.receiveShadows = true;
      shadows.addShadowCaster(mesh, false);
      mesh.isPickable = choice !== undefined || key === "alex" || key === "sam";
      if (choice !== undefined) mesh.metadata = { choice };
    });
    instance.animationGroups.forEach((group) => group.stop());
    return { root, animations: instance.animationGroups };
  }
  function idle(room) {
    room.character?.animations.forEach((group) => group.stop());
    if (!reduced) room.character?.animations.find((group) => /(^|[-_])idle$/i.test(group.name))?.start(true);
  }
  async function buildRoom(name) {
    if (rooms.has(name)) return rooms.get(name);
    const promise = (async () => {
      const root = new TransformNode(name, scene);
      root.setEnabled(false);
      const floor = CreateGround(name + "-floor", { width: 8.4, height: 6.5 }, scene);
      floor.parent = root; floor.material = palette.floor; floor.isPickable = false;
      floor.receiveShadows = true;
      box("back-wall", root, [8.4, 3.5, .16], [0, 1.75, 2.8], name === "cafe" ? palette.cream : palette.pale);
      box("side-wall", root, [.16, 3.5, 4.7], [-4.1, 1.75, .5], palette.cream);
      box("skirting", root, [8.4, .14, .2], [0, .09, 2.68], palette.green);
      box("window-frame", root, [1.9, 1.7, .16], [-2.45, 2.15, 2.65], palette.green);
      box("window-glass", root, [1.65, 1.45, .18], [-2.45, 2.15, 2.52], palette.glass);
      box("window-middle", root, [.07, 1.5, .21], [-2.45, 2.15, 2.4], palette.cream);
      box("window-middle-h", root, [1.65, .07, .21], [-2.45, 2.15, 2.4], palette.cream);
      let character;
      if (name === "cafe") {
        sign("cafe-name", root, ["HELLO, COFFEE!"], [.8, 2.85, 2.61], 3.9, .65);
        for (let i = 0; i < 9; i++) box("awning-" + i, root, [.42, .12, .65], [-.9 + i * .42, 2.34, 2.3], i % 2 ? palette.cream : palette.orange);
        await Promise.all([
          place("counter", root, [.65, 0, .75], 1.1).then((item) => { item.root.scaling.x *= 3; }),
          place("coffeeMachine", root, [1.8, 1.1, 1.0], .55),
          place("plant", root, [-3.1, 0, 1.8], 1.3),
          place("table", root, [-2.6, 0, -1.1], .85),
          place("chair", root, [-3.3, 0, -.7], 1.0, .7),
          place("coffee", root, [-2.6, .86, -1.1], .22),
          place("apple", root, [-.75, 1.12, -.02], .3, 0, 0),
          place("coffee", root, [.15, 1.12, -.02], .32, 0, 1),
          place("sandwich", root, [1.05, 1.12, -.02], .3, 0, 2),
        ]);
        sign("hours", root, ["MON - FRI", "8 AM - 6 PM"], [2.9, 1.9, 2.58], 1.0, .7);
        character = await place("alex", root, [.55, 0, 1.65], 1.8, Math.PI);
      } else {
        sign("meeting-name", root, ["LET'S MEET."], [.65, 2.85, 2.61], 3.3, .65);
        await Promise.all([
          place("reception", root, [.85, 0, .7], 1.05),
          place("bench", root, [-2.65, 0, 1.0], .9),
          place("plant", root, [-3.1, 0, -.8], 1.45),
          place("bookcase", root, [2.95, 0, 2.1], 1.85),
          place("books", root, [.8, 1.05, .7], .25),
          place("lamp", root, [2.8, 0, -.9], 1.8),
        ]);
        sign("room-two", root, ["ROOM 2", "WELCOME"], [-1.0, 1.9, 2.58], 1.1, .75);
        character = await place("sam", root, [.75, 0, 1.65], 1.8, Math.PI);
      }
      return { root, character };
    })();
    rooms.set(name, promise);
    return promise;
  }

  scene.onPointerObservable.add((info) => {
    if (info.type !== PointerEventTypes.POINTERPICK || activeQuestion?.interaction !== "objects") return;
    const choice = info.pickInfo?.pickedMesh?.metadata?.choice;
    if (choice !== undefined) onChoice(choice);
  });
  let lastFrame = 0;
  engine.runRenderLoop(() => {
    const now = performance.now();
    if (!disposed && !document.hidden && now - lastFrame >= 32) {
      scene.render();
      lastFrame = now;
    }
  });

  return {
    async show(question) {
      const ownGeneration = ++generation;
      const room = await buildRoom(question.scene);
      if (disposed || ownGeneration !== generation) return;
      activeRoom?.root.setEnabled(false);
      activeRoom?.character.animations.forEach((group) => group.stop());
      activeRoom = room;
      activeQuestion = question;
      room.root.setEnabled(true);
      idle(room);
      resize();
      // Preload only the next scene's unique models, without enabling them.
      if (question.position === 2 && !navigator.connection?.saveData && !/2g/.test(navigator.connection?.effectiveType || "")) {
        ["sam", "reception", "bench", "bookcase", "books", "lamp"].forEach((key) => { load(key).catch(() => {}); });
      }
    },
    react() {
      if (!activeRoom || reduced || disposed) return;
      clearTimeout(reactionTimer);
      activeRoom.character.animations.forEach((group) => group.stop());
      activeRoom.character.animations.find((group) => /emote-yes$/i.test(group.name))?.start(false);
      reactionTimer = setTimeout(() => { if (!disposed && activeRoom) idle(activeRoom); }, 1400);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      clearTimeout(reactionTimer);
      observer.disconnect();
      engine.stopRenderLoop();
      scene.dispose();
      engine.dispose();
    },
  };
}
