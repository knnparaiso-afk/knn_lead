/**
 * witch-game.js - Witch's Potion 3D Engine & Game Controller
 * Otimizado para alto desempenho e baixo tráfego mobile.
 */
(function () {
    'use strict';

    const cfg = window.WITCH_CONFIG || {};
    const modelUrl = cfg.modelUrl || '/static/models/model.glb';
    const cauldronUrl = cfg.cauldronUrl || '/static/models/cauldron.glb';
    const ingredientsBaseUrl = cfg.ingredientsBaseUrl || '/static/models/ingredients/';
    const backgroundUrl = cfg.backgroundUrl || '/static/images/witch-forest-background.webp';
    const participarUrl = cfg.participarUrl || '/participar';
    const responderUrl = cfg.responderUrl || '';
    const hasCustomCauldron = Boolean(cfg.hasCustomCauldron);
    const ingredientUrls = cfg.ingredientUrls && typeof cfg.ingredientUrls === 'object' ? cfg.ingredientUrls : {};
    const MODEL_LOAD_TIMEOUT_MS = 30000;

    function loadGltf(url) {
        return new Promise((resolve, reject) => {
            let finished = false;
            const complete = (callback, value) => {
                if (finished) return;
                finished = true;
                clearTimeout(timer);
                callback(value);
            };
            const timer = setTimeout(() => {
                complete(reject, new Error(`Tempo esgotado ao carregar ${url}`));
            }, MODEL_LOAD_TIMEOUT_MS);
            try {
                new THREE.GLTFLoader().load(
                    url,
                    gltf => complete(resolve, gltf),
                    undefined,
                    error => complete(reject, error || new Error(`Falha ao carregar ${url}`))
                );
            } catch (error) {
                complete(reject, error);
            }
        });
    }

    // ========================================================
    // 1. ÁUDIO PROCEDURAL (ZERO DOWNLOADS DE ARQUIVOS DE SOM)
    // ========================================================
    class SoundFX {
        constructor() {
            this.ctx = null;
            this.muted = false;
        }

        _init() {
            if (!this.ctx) {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) this.ctx = new AudioCtx();
            }
            if (this.ctx && this.ctx.state === 'suspended') {
                this.ctx.resume();
            }
        }

        toggleMute() {
            this.muted = !this.muted;
            return this.muted;
        }

        playCorrect() {
            if (this.muted) return;
            this._init();
            if (!this.ctx) return;
            const now = this.ctx.currentTime;
            [523.25, 659.25, 783.99, 1046.50].forEach((f, i) => {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(f, now + i * 0.07);
                gain.gain.setValueAtTime(0.001, now + i * 0.07);
                gain.gain.exponentialRampToValueAtTime(0.2, now + i * 0.07 + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.07 + 0.4);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now + i * 0.07);
                osc.stop(now + i * 0.07 + 0.45);
            });
        }

        playSpawn() {
            if (this.muted) return;
            this._init();
            if (!this.ctx) return;
            const now = this.ctx.currentTime;
            [440, 554, 659].forEach((freq, idx) => {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(freq, now + idx * 0.08);
                gain.gain.setValueAtTime(0.001, now + idx * 0.08);
                gain.gain.exponentialRampToValueAtTime(0.14, now + idx * 0.08 + 0.015);
                gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.22);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now + idx * 0.08);
                osc.stop(now + idx * 0.08 + 0.25);
            });
        }

        playSplash() {
            if (this.muted) return;
            this._init();
            if (!this.ctx) return;
            const now = this.ctx.currentTime;
            const bufferSize = this.ctx.sampleRate * 0.28;
            const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

            const noise = this.ctx.createBufferSource();
            noise.buffer = buffer;
            const filter = this.ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(700, now);
            filter.frequency.exponentialRampToValueAtTime(250, now + 0.25);
            filter.Q.value = 3.0;

            const gain = this.ctx.createGain();
            gain.gain.setValueAtTime(0.25, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.28);

            noise.connect(filter);
            filter.connect(gain);
            gain.connect(this.ctx.destination);
            noise.start(now);
        }

        playWrong() {
            if (this.muted) return;
            this._init();
            if (!this.ctx) return;
            const now = this.ctx.currentTime;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(240, now);
            osc.frequency.exponentialRampToValueAtTime(110, now + 0.25);
            gain.gain.setValueAtTime(0.18, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start(now);
            osc.stop(now + 0.32);
        }

        playVictory() {
            if (this.muted) return;
            this._init();
            if (!this.ctx) return;
            const now = this.ctx.currentTime;
            [440, 554, 659, 880].forEach((f, i) => {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(f, now + i * 0.1);
                gain.gain.setValueAtTime(0.2, now + i * 0.1);
                gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.1 + 0.5);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now + i * 0.1);
                osc.stop(now + i * 0.1 + 0.55);
            });
        }
    }

    const sound = new SoundFX();

    // ========================================================
    // 2. BANCO DE 20 INGREDIENTES E GERADOR DINÂMICO
    // ========================================================
    const INGREDIENTS_DATABASE = [
        { id: "magic_mushrooms", name: "Magic Mushrooms", namePt: "Cogumelos Mágicos", prefixEn: "Pick the", icon: "🍄" },
        { id: "spell_book", name: "Spell Book", namePt: "Livro de Feitiços", prefixEn: "Open the", icon: "📖" },
        { id: "blue_potion", name: "Blue Potion", namePt: "Poção Azul", prefixEn: "Pour the", icon: "🧪" },
        { id: "green_potion", name: "Green Potion", namePt: "Poção Verde", prefixEn: "Pour the", icon: "🧪" },
        { id: "red_potion", name: "Red Potion", namePt: "Poção Vermelha", prefixEn: "Pour the", icon: "🧪" },
        { id: "magic_crystal", name: "Magic Crystal", namePt: "Cristal Mágico", prefixEn: "Drop the", icon: "💎" },
        { id: "crystal_amulet", name: "Crystal Amulet", namePt: "Amuleto de Cristal", prefixEn: "Place the", icon: "🧿" },
        { id: "ancient_scroll", name: "Ancient Scroll", namePt: "Pergaminho Antigo", prefixEn: "Read the", icon: "📜" },
        { id: "mortar_pestle", name: "Mortar and Pestle", namePt: "Almofariz e Pilão", prefixEn: "Grind with the", icon: "🥣" },
        { id: "ingredient_jar", name: "Ingredient Jar", namePt: "Pote de Ingredientes", prefixEn: "Open the", icon: "🫙" },
        { id: "magic_pouch", name: "Magic Pouch", namePt: "Bolsa de Magia", prefixEn: "Empty the", icon: "👛" },
        { id: "magic_vial", name: "Magic Vial", namePt: "Frasco Mágico", prefixEn: "Add the", icon: "⚗️" },
        { id: "magic_candle", name: "Magic Candle", namePt: "Vela Mágica", prefixEn: "Light the", icon: "🕯️" },
        { id: "witch_staff", name: "Witch Staff", namePt: "Cajado da Bruxa", prefixEn: "Wave the", icon: "🪄" },
        { id: "golden_key", name: "Golden Key", namePt: "Chave Dourada", prefixEn: "Turn the", icon: "🗝️" },
        { id: "magic_coin", name: "Magic Coin", namePt: "Moeda Mágica", prefixEn: "Toss the", icon: "🪙" },
        { id: "treasure_chest", name: "Treasure Chest", namePt: "Baú do Tesouro", prefixEn: "Unlock the", icon: "📦" },
        { id: "magic_box", name: "Magic Box", namePt: "Caixa Mágica", prefixEn: "Inspect the", icon: "📦" },
        { id: "wooden_lid", name: "Wooden Lid", namePt: "Tampa de Madeira", prefixEn: "Lift the", icon: "🪵" },
        { id: "mini_cauldron", name: "Mini Cauldron", namePt: "Mini Caldeirão", prefixEn: "Stir the", icon: "🫕" }
    ];

    function generateDynamicRecipes() {
        const catalog = [...INGREDIENTS_DATABASE];
        for (let i = catalog.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [catalog[i], catalog[j]] = [catalog[j], catalog[i]];
        }

        const recipeMeta = [
            { name: "Poção Iniciante", tag: "Receita 1/3", steps: 2 },
            { name: "Mistura ao Luar", tag: "Receita 2/3", steps: 2 },
            { name: "Chama do Dragão", tag: "Receita 3/3", steps: 2 }
        ];

        const targetPool = catalog.slice(0, 6);
        const distractorPool = catalog.slice(6);

        let distractorIdx = 0;
        let targetIdx = 0;

        return recipeMeta.map(rm => {
            const tasks = [];
            for (let s = 0; s < rm.steps; s++) {
                const targetItem = targetPool[targetIdx++];
                const d1 = distractorPool[distractorIdx % distractorPool.length];
                distractorIdx++;
                const d2 = distractorPool[distractorIdx % distractorPool.length];
                distractorIdx++;

                tasks.push({
                    target: targetItem.id,
                    prefixEn: targetItem.prefixEn,
                    keywordEn: targetItem.name,
                    distractors: [d1.id, d2.id]
                });
            }
            return {
                name: rm.name,
                tag: rm.tag,
                tasks: tasks
            };
        });
    }

    // ========================================================
    // 3. ENGINE 3D (THREE.JS) — ENQUADRAMENTO PERFEITO E CACHE
    // ========================================================
    class WitchScene3D {
        constructor() {
            this.canvas = document.getElementById('webgl-canvas');
            this.container = document.getElementById('viewport-wrapper');

            this.scene = null;
            this.camera = null;
            this.renderer = null;
            this.clock = new THREE.Clock();

            this.witch = null;
            this.cauldron = null;
            this.cauldronLight = null;
            this.cauldronLiquid = null;
            this.bubbles = [];
            this.magicDust = null;

            this.ingredients = {};
            this.interactiveObjects = [];
            this.raycaster = new THREE.Raycaster();
            this.mouse = new THREE.Vector2();

            this.flyingItem = null;
            this.spawnAnimations = [];
            this.shrinkAnimations = [];
            this.activeIngredientIds = [];
            this.isReady = false;
            this.isBusy = false;

            this.init();
        }

        init() {
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0x241040);
            this.scene.fog = new THREE.FogExp2(0x1a0c31, 0.075);

            const w = this.container.clientWidth;
            const h = this.container.clientHeight;
            this.camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 50);
            this._updateCamera();

            this.renderer = new THREE.WebGLRenderer({
                canvas: this.canvas,
                antialias: true,
                powerPreference: 'high-performance'
            });
            this.renderer.setSize(w, h);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            this.renderer.outputEncoding = THREE.sRGBEncoding;
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

            this._setupLighting();
            this._buildEnvironment();
            this._buildCauldron();

            window.addEventListener('resize', () => this.onResize());
            this.canvas.addEventListener('click', (e) => this.onPointer(e.clientX, e.clientY));
            this.canvas.addEventListener('touchstart', (e) => {
                if (e.touches.length > 0) {
                    this.onPointer(e.touches[0].clientX, e.touches[0].clientY);
                }
            }, { passive: true });

            this.animate = this.animate.bind(this);
            requestAnimationFrame(this.animate);
        }

        _updateCamera() {
            const aspect = this.container.clientWidth / this.container.clientHeight;
            if (aspect < 0.8) {
                // Smartphone vertical (Portrait)
                this.camera.position.set(0, 1.85, 3.5);
                this.camera.lookAt(0, 1.05, 0);
            } else {
                // Desktop horizontal (Landscape)
                this.camera.position.set(0, 1.65, 3.1);
                this.camera.lookAt(0, 1.1, 0);
            }
        }

        _setupLighting() {
            const ambient = new THREE.AmbientLight(0x5b2594, 1.5);
            this.scene.add(ambient);

            const moonLight = new THREE.DirectionalLight(0xfff7ed, 1.2);
            moonLight.position.set(2, 6, 3);
            moonLight.castShadow = true;
            moonLight.shadow.mapSize.width = 1024;
            moonLight.shadow.mapSize.height = 1024;
            this.scene.add(moonLight);

            this.cauldronLight = new THREE.PointLight(0x39ff14, 2.8, 4.5);
            this.cauldronLight.position.set(0.38, 1.05, -0.15);
            this.scene.add(this.cauldronLight);

            const warmLight = new THREE.PointLight(0xd8b4fe, 0.8, 5.0);
            warmLight.position.set(1.4, 2.0, 1.0);
            this.scene.add(warmLight);
        }

        _buildEnvironment() {
            const floor = new THREE.Mesh(
                new THREE.PlaneGeometry(14, 14),
                new THREE.MeshStandardMaterial({ color: 0x140e22, roughness: 0.9 })
            );
            floor.rotation.x = -Math.PI / 2;
            floor.receiveShadow = true;
            this.scene.add(floor);

            const wall = new THREE.Mesh(
                new THREE.PlaneGeometry(14, 8),
                new THREE.MeshStandardMaterial({ color: 0x0f091c, roughness: 0.95 })
            );
            wall.position.set(0, 4, -3.2);
            this.scene.add(wall);

            const dustCount = 70;
            const dustGeo = new THREE.BufferGeometry();
            const pos = new Float32Array(dustCount * 3);
            for (let i = 0; i < dustCount * 3; i += 3) {
                pos[i] = (Math.random() - 0.5) * 6;
                pos[i + 1] = Math.random() * 4 + 0.3;
                pos[i + 2] = (Math.random() - 0.5) * 4.5;
            }
            dustGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
            this.magicDust = new THREE.Points(
                dustGeo,
                new THREE.PointsMaterial({
                    color: 0xa855f7,
                    size: 0.045,
                    transparent: true,
                    opacity: 0.65,
                    blending: THREE.AdditiveBlending
                })
            );
            this.scene.add(this.magicDust);

            // MESA DE ALQUIMIA NA FRENTE
            const tableMat = new THREE.MeshStandardMaterial({ color: 0x3d2514, roughness: 0.75, metalness: 0.05 });
            const tableTop = new THREE.Mesh(new THREE.BoxGeometry(1.80, 0.10, 1.05), tableMat);
            tableTop.position.set(0, 0.50, 0.85);
            tableTop.receiveShadow = true;
            tableTop.castShadow = true;
            this.scene.add(tableTop);

            const legGeo = new THREE.CylinderGeometry(0.045, 0.04, 0.50, 8);
            [[-0.78, 0.25, 1.25], [0.78, 0.25, 1.25], [-0.78, 0.25, 0.45], [0.78, 0.25, 0.45]].forEach(p => {
                const leg = new THREE.Mesh(legGeo, tableMat);
                leg.position.set(...p);
                leg.castShadow = true;
                this.scene.add(leg);
            });
        }

        _loadForestBackground() {
            const textureLoader = new THREE.TextureLoader();
            textureLoader.load(backgroundUrl, texture => {
                texture.encoding = THREE.sRGBEncoding;
                const backdrop = new THREE.Mesh(
                    new THREE.PlaneGeometry(14, 7.875),
                    new THREE.MeshBasicMaterial({
                        map: texture,
                        transparent: true,
                        opacity: 0.9,
                        depthWrite: false
                    })
                );
                backdrop.position.set(0, 3.2, -3.12);
                this.scene.add(backdrop);
            }, undefined, () => {});
        }

        _buildCauldron() {
            const grp = new THREE.Group();
            grp.position.set(0.38, 0, -0.15);

            const procCauldron = new THREE.Group();
            const ironMat = new THREE.MeshStandardMaterial({
                color: 0x14111d,
                roughness: 0.5,
                metalness: 0.82
            });
            const bronzeMat = new THREE.MeshStandardMaterial({
                color: 0xc27803,
                roughness: 0.35,
                metalness: 0.85
            });

            const belly = new THREE.Mesh(new THREE.SphereGeometry(0.50, 26, 22), ironMat);
            belly.scale.set(1.05, 0.88, 1.05);
            belly.position.y = 0.50;
            belly.castShadow = true;
            belly.receiveShadow = true;
            procCauldron.add(belly);

            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.44, 0.40, 0.16, 26), ironMat);
            neck.position.y = 0.80;
            neck.castShadow = true;
            procCauldron.add(neck);

            const rim = new THREE.Mesh(new THREE.TorusGeometry(0.45, 0.055, 14, 32), ironMat);
            rim.rotation.x = Math.PI / 2;
            rim.position.y = 0.88;
            rim.castShadow = true;
            procCauldron.add(rim);

            const band = new THREE.Mesh(new THREE.TorusGeometry(0.465, 0.016, 10, 32), bronzeMat);
            band.rotation.x = Math.PI / 2;
            band.position.y = 0.81;
            procCauldron.add(band);

            const legGeo = new THREE.CylinderGeometry(0.045, 0.075, 0.24, 8);
            legGeo.rotateZ(0.12);
            for (let i = 0; i < 3; i++) {
                const a = (i * Math.PI * 2) / 3;
                const leg = new THREE.Mesh(legGeo, ironMat);
                leg.position.set(Math.cos(a) * 0.35, 0.12, Math.sin(a) * 0.35);
                leg.rotation.y = -a;
                leg.castShadow = true;
                procCauldron.add(leg);
            }

            [-0.52, 0.52].forEach(xPos => {
                const handleMount = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.08), ironMat);
                handleMount.position.set(xPos, 0.65, 0);
                procCauldron.add(handleMount);

                const ring = new THREE.Mesh(new THREE.TorusGeometry(0.09, 0.02, 10, 20), bronzeMat);
                ring.position.set(xPos + (xPos > 0 ? 0.04 : -0.04), 0.60, 0);
                ring.rotation.y = Math.PI / 2;
                ring.rotation.x = 0.2;
                procCauldron.add(ring);
            });

            const emberMat = new THREE.MeshStandardMaterial({
                color: 0xff3b00,
                emissive: 0xff4500,
                emissiveIntensity: 2.2,
                roughness: 0.6
            });
            for (let i = 0; i < 7; i++) {
                const ang = Math.random() * Math.PI * 2;
                const dist = Math.random() * 0.26;
                const ember = new THREE.Mesh(new THREE.DodecahedronGeometry(0.035 + Math.random() * 0.03), emberMat);
                ember.position.set(Math.cos(ang) * dist, 0.035, Math.sin(ang) * dist);
                procCauldron.add(ember);
            }

            const fireLight = new THREE.PointLight(0xff4500, 1.4, 1.8);
            fireLight.position.set(0, 0.08, 0);
            procCauldron.add(fireLight);

            grp.add(procCauldron);

            const liquidGeo = new THREE.CircleGeometry(0.40, 26);
            liquidGeo.rotateX(-Math.PI / 2);
            this.cauldronLiquid = new THREE.Mesh(
                liquidGeo,
                new THREE.MeshStandardMaterial({
                    color: 0x15803d,
                    emissive: 0x22c55e,
                    emissiveIntensity: 0.95,
                    roughness: 0.18
                })
            );
            this.cauldronLiquid.position.y = 0.74;
            grp.add(this.cauldronLiquid);

            const bMat = new THREE.MeshStandardMaterial({
                color: 0x86efac,
                emissive: 0x39ff14,
                emissiveIntensity: 1.2,
                transparent: true,
                opacity: 0.85
            });
            for (let i = 0; i < 7; i++) {
                const b = new THREE.Mesh(new THREE.SphereGeometry(0.028 + Math.random() * 0.032, 10, 8), bMat);
                b.userData = {
                    baseY: 0.74,
                    speed: 0.35 + Math.random() * 0.55,
                    maxH: 0.30 + Math.random() * 0.25,
                    angle: Math.random() * Math.PI * 2,
                    dist: Math.random() * 0.26
                };
                grp.add(b);
                this.bubbles.push(b);
            }

            this.proceduralCauldron = procCauldron;
            this.cauldron = grp;
            this.scene.add(this.cauldron);
        }

        _loadCustomCauldron() {
            if (!hasCustomCauldron || this.customCauldronLoaded) return Promise.resolve();
            if (this.cauldronLoadPromise) return this.cauldronLoadPromise;

            this.cauldronLoadPromise = loadGltf(cauldronUrl).then(gltf => {
                const m = gltf.scene;
                if (!m) throw new Error('Modelo do caldeirão vazio.');
                const box = new THREE.Box3().setFromObject(m);
                const size = box.getSize(new THREE.Vector3());
                const center = box.getCenter(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                if (maxDim > 0) {
                    const targetScale = 1.15 / maxDim;
                    m.scale.set(targetScale, targetScale, targetScale);
                    m.position.x = -center.x * targetScale;
                    m.position.y = -box.min.y * targetScale;
                    m.position.z = -center.z * targetScale;
                }
                m.traverse(node => {
                    if (node.isMesh) {
                        node.castShadow = true;
                        node.receiveShadow = true;
                    }
                });
                this.proceduralCauldron.visible = false;
                this.cauldron.add(m);
                this.customCauldronLoaded = true;
            }).catch(error => {
                console.warn('Caldeirão 3D indisponível; usando o modelo simples.', error);
            });
            return this.cauldronLoadPromise;
        }

        _createWoodLabel(name, icon) {
            const canvas = document.createElement('canvas');
            canvas.width = 320;
            canvas.height = 96;
            const ctx = canvas.getContext('2d');

            ctx.fillStyle = '#1c120a';
            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = 5;
            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(4, 4, 312, 88, 12);
            } else {
                const x = 4, y = 4, w = 312, h = 88, r = 12;
                ctx.moveTo(x + r, y);
                ctx.lineTo(x + w - r, y);
                ctx.quadraticCurveTo(x + w, y, x + w, y + r);
                ctx.lineTo(x + w, y + h - r);
                ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
                ctx.lineTo(x + r, y + h);
                ctx.quadraticCurveTo(x, y + h, x, y + h - r);
                ctx.lineTo(x, y + r);
                ctx.quadraticCurveTo(x, y, x + r, y);
                ctx.closePath();
            }
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#fef3c7';
            ctx.font = 'bold 28px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${icon || '✨'} ${name}`, 160, 48);

            const texture = new THREE.CanvasTexture(canvas);
            const mat = new THREE.MeshBasicMaterial({ map: texture, transparent: true });
            const geo = new THREE.PlaneGeometry(0.28, 0.085);
            return new THREE.Mesh(geo, mat);
        }

        /**
         * Constrói um ingrediente já com o GLB pré-carregado (via this.glbCache).
         * Sem modelo procedural — o GLB é sempre a fonte única da geometria.
         */
        getOrCreateIngredient(id) {
            if (this.ingredients[id]) return this.ingredients[id];

            const item = INGREDIENTS_DATABASE.find(i => i.id === id);
            const cachedGltf = this.glbCache && this.glbCache[id];
            if (!item || !cachedGltf || !cachedGltf.scene) {
                throw new Error(`Ingrediente ${id} não está pronto.`);
            }

            const surfaceY = 0.55;
            const grp = new THREE.Group();
            grp.position.set(0, surfaceY, 0.85);
            grp.userData = {
                id: item.id,
                name: item.name,
                namePt: item.namePt,
                basePos: new THREE.Vector3(0, surfaceY, 0.85),
                hitMeshList: []
            };

            const plate = new THREE.Mesh(
                new THREE.CylinderGeometry(0.16, 0.17, 0.025, 16),
                new THREE.MeshStandardMaterial({ color: 0x22150a, roughness: 0.85 })
            );
            plate.position.y = 0.0125;
            plate.receiveShadow = true;
            grp.add(plate);

            // Usa o GLB pré-carregado do cache (sem fallback procedural)
            if (cachedGltf) {
                const m = cachedGltf.scene.clone();
                const box = new THREE.Box3().setFromObject(m);
                const size = box.getSize(new THREE.Vector3());
                const center = box.getCenter(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                if (maxDim > 0) {
                    let targetDim = 0.30;
                    if (item.id === 'magic_coin') targetDim = 0.22;
                    else if (item.id === 'golden_key') targetDim = 0.26;
                    else if (item.id === 'witch_staff') targetDim = 0.38;
                    else if (item.id === 'treasure_chest' || item.id === 'magic_box' || item.id === 'wooden_lid') targetDim = 0.32;
                    else if (item.id === 'mini_cauldron') targetDim = 0.28;
                    else if (item.id === 'ancient_scroll' || item.id === 'spell_book') targetDim = 0.30;
                    else if (item.id.includes('potion') || item.id === 'magic_vial') targetDim = 0.28;

                    const s = targetDim / maxDim;
                    m.scale.set(s, s, s);
                    m.position.x = -center.x * s;
                    m.position.y = 0.025 - box.min.y * s;
                    m.position.z = -center.z * s;

                    if (item.id === 'witch_staff') m.rotation.z = Math.PI / 8;
                }
                m.traverse(node => {
                    if (node.isMesh) {
                        node.castShadow = true;
                        node.receiveShadow = true;
                        node.userData.ingredientId = item.id;
                        grp.userData.hitMeshList.push(node);
                    }
                });
                grp.add(m);
            }

            const labelMesh = this._createWoodLabel(item.namePt, item.icon);
            labelMesh.position.set(0, 0.02, 0.17);
            labelMesh.rotation.x = -Math.PI / 4;
            grp.add(labelMesh);

            const hitGeo = new THREE.CylinderGeometry(0.20, 0.20, 0.55, 12);
            const hitMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.0001, depthWrite: false });
            const hitBox = new THREE.Mesh(hitGeo, hitMat);
            hitBox.position.y = 0.25;
            hitBox.userData = { ingredientId: item.id };
            grp.add(hitBox);
            grp.userData.hitMeshList.push(hitBox);

            grp.visible = false;
            grp.scale.set(0.0001, 0.0001, 0.0001);

            this.ingredients[item.id] = grp;
            this.scene.add(grp);
            return grp;
        }

        _showLoading(message) {
            const overlay = document.getElementById('loading-overlay');
            const status = document.getElementById('loading-status');
            const bar = document.getElementById('loading-bar');
            const retry = document.getElementById('btn-retry-loading');
            clearTimeout(this.loadingHideTimer);
            if (overlay) {
                overlay.style.display = 'flex';
                overlay.style.opacity = '1';
                overlay.style.pointerEvents = 'auto';
            }
            if (status) status.textContent = message;
            if (bar) bar.style.width = '0%';
            if (retry) retry.style.display = 'none';
        }

        _updateLoading(completed, total) {
            const bar = document.getElementById('loading-bar');
            if (bar) bar.style.width = `${Math.round(100 * completed / total)}%`;
        }

        _showLoadError(onRetry) {
            const status = document.getElementById('loading-status');
            const retry = document.getElementById('btn-retry-loading');
            if (status) status.textContent = 'Não foi possível carregar os modelos. Confira sua conexão e tente novamente.';
            if (retry) {
                retry.onclick = onRetry;
                retry.style.display = 'block';
            }
        }

        _hideLoading() {
            const overlay = document.getElementById('loading-overlay');
            if (!overlay) return;
            overlay.style.opacity = '0';
            overlay.style.pointerEvents = 'none';
            clearTimeout(this.loadingHideTimer);
            this.loadingHideTimer = setTimeout(() => { overlay.style.display = 'none'; }, 500);
        }

        _loadWitchModel() {
            if (this.witchModelLoaded) return Promise.resolve();
            if (this.witchLoadPromise) return this.witchLoadPromise;
            const load = loadGltf(modelUrl).then(gltf => {
                const model = gltf.scene;
                if (!model) throw new Error('Modelo da bruxa vazio.');
                model.scale.set(0.92, 0.92, 0.92);
                model.position.set(-0.42, 0, -0.32);
                model.rotation.y = 0.35;
                model.traverse(node => {
                    if (node.isMesh) { node.castShadow = true; node.receiveShadow = true; }
                });
                this.scene.add(model);
                this.witchModelLoaded = true;
                if (window.WitchReactions) {
                    try {
                        this.witch = new window.WitchReactions();
                        this.witch.init(gltf);
                    } catch (error) {
                        console.warn('Animação da bruxa indisponível.', error);
                    }
                }
            });
            this.witchLoadPromise = load;
            load.catch(() => { this.witchLoadPromise = null; });
            return load;
        }

        _loadIngredient(id) {
            if (this.glbCache[id]) return Promise.resolve(this.glbCache[id]);
            if (this.ingredientLoads[id]) return this.ingredientLoads[id];
            const url = ingredientUrls[id] || `${ingredientsBaseUrl}${id}.glb`;
            const load = loadGltf(url).then(gltf => {
                if (!gltf || !gltf.scene) throw new Error(`Modelo do ingrediente ${id} vazio.`);
                this.glbCache[id] = gltf;
                return gltf;
            });
            this.ingredientLoads[id] = load;
            load.then(
                () => { delete this.ingredientLoads[id]; },
                () => { delete this.ingredientLoads[id]; }
            );
            return load;
        }

        async ensureIngredients(ids, onProgress) {
            let completed = 0;
            const results = await Promise.allSettled(ids.map(id =>
                this._loadIngredient(id).finally(() => {
                    completed++;
                    if (onProgress) onProgress(completed, ids.length);
                })
            ));
            if (results.some(result => result.status === 'rejected')) {
                throw new Error('Um ou mais ingredientes não carregaram.');
            }
        }

        async prepareFirstTask(task, onReady) {
            this._showLoading('Carregando bruxa, caldeirão e ingredientes do primeiro passo...');
            if (!this.glbCache) this.glbCache = {};
            if (!this.ingredientLoads) this.ingredientLoads = {};
            const ids = [task.target, ...task.distractors];
            const total = ids.length + 2;
            let completed = 0;
            const track = promise => promise.finally(() => this._updateLoading(++completed, total));
            const results = await Promise.allSettled([
                track(this._loadWitchModel()),
                track(this._loadCustomCauldron()),
                ...ids.map(id => track(this._loadIngredient(id)))
            ]);
            if (results.some(result => result.status === 'rejected')) {
                this._showLoadError(() => this.prepareFirstTask(task, onReady));
                return;
            }
            this.isReady = true;
            this._hideLoading();
            this._loadForestBackground();
            if (onReady) onReady();
        }

        onPointer(clientX, clientY) {
            if (!this.isReady || this.isBusy) return;

            const rect = this.canvas.getBoundingClientRect();
            this.mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;

            this.raycaster.setFromCamera(this.mouse, this.camera);
            const hits = this.raycaster.intersectObjects(this.interactiveObjects, true);

            if (hits.length > 0) {
                let targetId = null;
                for (let hit of hits) {
                    let obj = hit.object;
                    while (obj) {
                        if (obj.userData && obj.userData.ingredientId) {
                            targetId = obj.userData.ingredientId;
                            break;
                        }
                        if (obj.userData && obj.userData.id) {
                            targetId = obj.userData.id;
                            break;
                        }
                        obj = obj.parent;
                    }
                    if (targetId) break;
                }

                if (targetId && window.gameLogic) {
                    window.gameLogic.selectIngredient(targetId);
                }
            }
        }

        spawnActiveIngredients(activeIds) {
            this.activeIngredientIds = [...activeIds];
            this.interactiveObjects = [];

            const slots = [
                new THREE.Vector3(-0.38, 0.55, 0.84),
                new THREE.Vector3(0.00, 0.55, 0.87),
                new THREE.Vector3(0.38, 0.55, 0.84)
            ];

            sound.playSpawn();

            Object.keys(this.ingredients).forEach(id => {
                if (!activeIds.includes(id)) {
                    const grp = this.ingredients[id];
                    if (grp) {
                        grp.visible = false;
                        grp.scale.set(0.0001, 0.0001, 0.0001);
                    }
                }
            });

            const now = this.clock.getElapsedTime();

            activeIds.forEach((id, idx) => {
                const grp = this.getOrCreateIngredient(id);
                if (!grp) return;

                const slot = slots[idx];
                grp.position.copy(slot);
                grp.userData.basePos = slot.clone();
                grp.rotation.set(0, 0, 0);
                grp.visible = true;
                grp.scale.set(0.2, 0.2, 0.2);

                if (grp.userData.hitMeshList) {
                    grp.userData.hitMeshList.forEach(m => this.interactiveObjects.push(m));
                }

                this.spawnAnimations.push({
                    grp: grp,
                    basePos: slot.clone(),
                    startTime: now + idx * 0.08,
                    duration: 0.4
                });
            });
        }

        dismissOtherIngredients(excludeId) {
            const now = this.clock.getElapsedTime();
            if (this.activeIngredientIds) {
                this.activeIngredientIds.forEach(id => {
                    if (id !== excludeId) {
                        const grp = this.ingredients[id];
                        if (grp && grp.visible) {
                            this.shrinkAnimations.push({
                                grp: grp,
                                startTime: now,
                                duration: 0.32,
                                startScale: grp.scale.x
                            });
                        }
                    }
                });
            }
            this.interactiveObjects = [];
        }

        flyIngredient(id, onDone) {
            const item = this.ingredients[id];
            if (!item) {
                if (onDone) onDone();
                return;
            }

            const start = item.position.clone();
            const target = new THREE.Vector3(0.38, 0.85, -0.15);
            const peak = new THREE.Vector3(
                (start.x + target.x) / 2,
                1.95,
                (start.z + target.z) / 2
            );

            this.flyingItem = {
                mesh: item,
                start: start,
                peak: peak,
                target: target,
                t: 0,
                duration: 0.7,
                onComplete: () => {
                    this.flyingItem = null;
                    item.visible = false;
                    item.scale.set(0.0001, 0.0001, 0.0001);
                    sound.playSplash();
                    this.splashCauldron();
                    if (onDone) onDone();
                }
            };
        }

        splashCauldron() {
            if (this.cauldronLight) {
                this.cauldronLight.intensity = 5.0;
                setTimeout(() => this.cauldronLight.intensity = 2.8, 400);
            }
            if (this.cauldronLiquid) {
                this.cauldronLiquid.scale.set(1.15, 1.15, 1.15);
                setTimeout(() => this.cauldronLiquid.scale.set(1, 1, 1), 350);
            }
        }

        shakeIngredient(id) {
            const item = this.ingredients[id];
            if (!item) return;
            const base = item.userData.basePos;
            const startT = this.clock.getElapsedTime();
            const intv = setInterval(() => {
                const elap = this.clock.getElapsedTime() - startT;
                if (elap > 0.35) {
                    clearInterval(intv);
                    item.position.copy(base);
                } else {
                    item.position.x = base.x + Math.sin(elap * 50) * 0.04;
                }
            }, 16);
        }

        reactHappy() {
            if (this.witch) this.witch.triggerHappy(2.0);
        }

        reactDisapprove() {
            if (this.witch) this.witch.triggerDisapprove(1.6);
        }

        resetIngredients() {
            Object.values(this.ingredients).forEach(item => {
                item.position.copy(item.userData.basePos || new THREE.Vector3(0, 0, 0));
                item.rotation.set(0, 0, 0);
                item.scale.set(0.0001, 0.0001, 0.0001);
                item.visible = false;
            });
            this.flyingItem = null;
            this.spawnAnimations = [];
            this.shrinkAnimations = [];
            this.interactiveObjects = [];
            this.activeIngredientIds = [];
        }

        onResize() {
            if (!this.renderer || !this.camera) return;
            const w = this.container.clientWidth;
            const h = this.container.clientHeight;
            this.camera.aspect = w / h;
            this._updateCamera();
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(w, h);
        }

        animate() {
            requestAnimationFrame(this.animate);
            const delta = this.clock.getDelta();
            const time = this.clock.getElapsedTime();

            if (this.witch) {
                this.witch.update(delta);
            }

            this.bubbles.forEach(b => {
                b.position.y += b.userData.speed * delta;
                if (b.position.y > b.userData.baseY + b.userData.maxH) {
                    b.position.y = b.userData.baseY;
                    b.position.x = Math.cos(time + b.userData.angle) * b.userData.dist;
                    b.position.z = Math.sin(time + b.userData.angle) * b.userData.dist;
                }
            });

            if (this.spawnAnimations && this.spawnAnimations.length > 0) {
                this.spawnAnimations = this.spawnAnimations.filter(anim => {
                    if (time < anim.startTime) return true;
                    const p = Math.min(1.0, (time - anim.startTime) / anim.duration);
                    const c1 = 1.70158;
                    const c3 = c1 + 1;
                    const t = p - 1;
                    const eased = 1 + c3 * Math.pow(t, 3) + c1 * Math.pow(t, 2);
                    const s = Math.max(0.2, Math.min(1.25, eased * 1.15));
                    anim.grp.scale.set(s, s, s);
                    anim.grp.position.y = anim.basePos.y + (1 - p) * 0.10;

                    if (p >= 1.0) {
                        anim.grp.scale.set(1.15, 1.15, 1.15);
                        anim.grp.position.copy(anim.basePos);
                        return false;
                    }
                    return true;
                });
            }

            if (this.shrinkAnimations && this.shrinkAnimations.length > 0) {
                this.shrinkAnimations = this.shrinkAnimations.filter(anim => {
                    const p = Math.min(1.0, (time - anim.startTime) / anim.duration);
                    const s = Math.max(0.0001, anim.startScale * (1 - p));
                    anim.grp.scale.set(s, s, s);
                    if (p >= 1.0) {
                        anim.grp.visible = false;
                        anim.grp.scale.set(0.0001, 0.0001, 0.0001);
                        return false;
                    }
                    return true;
                });
            }

            if (this.flyingItem) {
                const f = this.flyingItem;
                f.t += delta / f.duration;
                if (f.t >= 1.0) {
                    f.mesh.position.copy(f.target);
                    f.mesh.scale.set(0.01, 0.01, 0.01);
                    f.onComplete();
                } else {
                    const t = f.t;
                    const inv = 1 - t;
                    f.mesh.position.x = inv * inv * f.start.x + 2 * inv * t * f.peak.x + t * t * f.target.x;
                    f.mesh.position.y = inv * inv * f.start.y + 2 * inv * t * f.peak.y + t * t * f.target.y;
                    f.mesh.position.z = inv * inv * f.start.z + 2 * inv * t * f.peak.z + t * t * f.target.z;
                    f.mesh.rotation.x += delta * 6;
                    f.mesh.rotation.y += delta * 7;
                }
            }

            if (this.magicDust) {
                this.magicDust.rotation.y = time * 0.035;
            }

            this.renderer.render(this.scene, this.camera);
        }
    }

    // ========================================================
    // 4. CONTROLADOR DA DINÂMICA DO JOGO (HUD + REGRAS)
    // ========================================================
    class GameController {
        constructor(view3D) {
            this.view3D = view3D;
            this.recipes = generateDynamicRecipes();
            this.recipeIdx = 0;
            this.taskIdx = 0;
            this.score = 0;
            this.mistakes = 0;
            this.isBusy = false;
            this.loadGeneration = 0;
            this.victoryConfirmed = false;
            this.confirmingVictory = false;

            this._bindUI();
        }

        _bindUI() {
            const btnStart = document.getElementById('btn-start-game');
            if (btnStart) btnStart.addEventListener('click', () => this.startGame());

            const btnNext = document.getElementById('btn-next-recipe');
            if (btnNext) btnNext.addEventListener('click', () => this.nextRecipe());

            const btnPlayAgain = document.getElementById('btn-play-again');
            if (btnPlayAgain) btnPlayAgain.addEventListener('click', () => this.restart());

            const btnAudio = document.getElementById('btn-audio-toggle');
            if (btnAudio) {
                btnAudio.addEventListener('click', () => {
                    const isMuted = sound.toggleMute();
                    const icon = document.getElementById('audio-icon');
                    if (icon) icon.textContent = isMuted ? '🔇' : '🔊';
                });
            }

            const btnClaim = document.getElementById('btn-claim-rewards');
            if (btnClaim) {
                btnClaim.addEventListener('click', () => {
                    if (this.victoryConfirmed) window.location.href = participarUrl;
                    else this._notifyBackendVictory();
                });
            }
        }

        startGame() {
            if (!this.view3D.isReady) return;
            const intro = document.getElementById('screen-intro');
            if (intro) intro.style.display = 'none';

            const hud = document.getElementById('screen-hud');
            if (hud) hud.style.display = 'block';

            this.loadCurrentTask();
        }

        currentTask() {
            return this.recipes[this.recipeIdx].tasks[this.taskIdx];
        }

        prefetchNextTask() {
            const recipe = this.recipes[this.recipeIdx];
            const nextTask = recipe.tasks[this.taskIdx + 1]
                || this.recipes[this.recipeIdx + 1]?.tasks[0];
            if (!nextTask) return;
            this.view3D.ensureIngredients([nextTask.target, ...nextTask.distractors])
                .catch(error => console.warn('Pré-carregamento do próximo passo falhou.', error));
        }

        async loadCurrentTask() {
            const generation = ++this.loadGeneration;
            const recipe = this.recipes[this.recipeIdx];
            const task = recipe.tasks[this.taskIdx];
            const ids = [task.target, ...task.distractors];
            this.isBusy = true;
            this.view3D.isBusy = true;
            if (!ids.every(id => this.view3D.glbCache[id])) {
                this.view3D._showLoading('Preparando ingredientes do próximo passo...');
            }

            try {
                await this.view3D.ensureIngredients(ids, (completed, total) => {
                    if (generation === this.loadGeneration) this.view3D._updateLoading(completed, total);
                });
                if (generation !== this.loadGeneration) return;
                this.mistakes = 0;

                const nameEl = document.getElementById('hud-recipe-name');
                if (nameEl) nameEl.textContent = `📜 ${recipe.tag}: ${recipe.name}`;

                const stepEl = document.getElementById('hud-step-pill');
                if (stepEl) stepEl.textContent = `Etapa ${this.taskIdx + 1}/${recipe.tasks.length}`;

                const enEl = document.getElementById('task-text-en');
                if (enEl) enEl.innerHTML = `${task.prefixEn} <span class="hud-keyword">${task.keywordEn}</span>!`;

                this.hideToast();

                const chosen3 = [...ids];
                for (let i = chosen3.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [chosen3[i], chosen3[j]] = [chosen3[j], chosen3[i]];
                }

                this.view3D.spawnActiveIngredients(chosen3);
                this.view3D._hideLoading();
                this.isBusy = false;
                this.view3D.isBusy = false;
                this.prefetchNextTask();
            } catch (error) {
                if (generation !== this.loadGeneration) return;
                console.error('Erro ao preparar ingredientes:', error);
                this.view3D._showLoading('Preparando ingredientes do próximo passo...');
                this.view3D._showLoadError(() => this.loadCurrentTask());
            }
        }

        selectIngredient(id) {
            if (this.isBusy || !this.view3D.isReady) return;

            const recipe = this.recipes[this.recipeIdx];
            const currentTask = recipe.tasks[this.taskIdx];

            if (id === currentTask.target) {
                this.isBusy = true;
                this.view3D.isBusy = true;

                sound.playCorrect();
                this.view3D.reactHappy();

                const pts = this.mistakes === 0 ? 100 : 50;
                this.score += pts;
                const scoreEl = document.getElementById('score-val');
                if (scoreEl) scoreEl.textContent = this.score;

                this.showToast(`✨ ACERTOU! +${pts} PTS!`, 'success');

                this.view3D.dismissOtherIngredients(id);

                this.view3D.flyIngredient(id, () => {
                    setTimeout(() => {
                        this.taskIdx++;
                        if (this.taskIdx >= recipe.tasks.length) {
                            this.finishRecipe();
                        } else {
                            this.loadCurrentTask();
                        }
                    }, 400);
                });
            } else {
                this.mistakes++;
                sound.playWrong();
                this.view3D.reactDisapprove();
                this.view3D.shakeIngredient(id);

                this.showToast(`❌ Não é esse! Observe a palavra em destaque e tente novamente!`, 'error');
            }
        }

        finishRecipe() {
            sound.playVictory();
            const recipe = this.recipes[this.recipeIdx];
            const titleEl = document.getElementById('recipe-done-title');
            if (titleEl) titleEl.textContent = `${recipe.name} Pronta!`;

            setTimeout(() => {
                const hud = document.getElementById('screen-hud');
                if (hud) hud.style.display = 'none';

                const doneScreen = document.getElementById('screen-recipe-done');
                if (doneScreen) doneScreen.style.display = 'flex';
            }, 600);
        }

        nextRecipe() {
            const doneScreen = document.getElementById('screen-recipe-done');
            if (doneScreen) doneScreen.style.display = 'none';

            this.recipeIdx++;
            this.taskIdx = 0;

            if (this.recipeIdx >= this.recipes.length) {
                this.showVictory();
            } else {
                this.view3D.resetIngredients();
                const hud = document.getElementById('screen-hud');
                if (hud) hud.style.display = 'block';
                this.loadCurrentTask();
            }
        }

        showVictory() {
            sound.playVictory();
            const hud = document.getElementById('screen-hud');
            if (hud) hud.style.display = 'none';

            const doneScreen = document.getElementById('screen-recipe-done');
            if (doneScreen) doneScreen.style.display = 'none';

            const victoryScreen = document.getElementById('screen-victory');
            if (victoryScreen) victoryScreen.style.display = 'flex';

            const finalScoreEl = document.getElementById('victory-final-score');
            if (finalScoreEl) finalScoreEl.textContent = this.score;

            this.view3D.reactHappy();
            this.victoryConfirmed = false;
            this._notifyBackendVictory();
        }

        async _notifyBackendVictory() {
            if (this.confirmingVictory || this.victoryConfirmed) return;
            const button = document.getElementById('btn-claim-rewards');
            const status = document.getElementById('victory-status');
            let serverMessage = '';
            this.confirmingVictory = true;
            if (button) {
                button.disabled = true;
                button.textContent = 'LIBERANDO SEU PRÊMIO...';
            }
            if (status) status.textContent = 'Confirmando sua vitória...';
            try {
                if (!responderUrl) throw new Error('Endereço de confirmação ausente.');
                const formData = new FormData();
                formData.append('resposta', 'GAME_COMPLETE');
                const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
                const response = await fetch(responderUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrf || '' },
                    body: formData,
                    credentials: 'same-origin'
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    serverMessage = result.mensagem || '';
                    throw new Error(serverMessage || 'Confirmação não recebida.');
                }
                this.victoryConfirmed = true;
                if (status) status.textContent = 'Vitória confirmada! Seu cadastro está liberado.';
                if (button) button.textContent = 'LIBERAR MEU PRÊMIO NA KNN ➔';
            } catch (e) {
                console.warn('Falha ao confirmar a vitória:', e);
                if (status) status.textContent = serverMessage
                    ? `${serverMessage} Toque para tentar novamente.`
                    : 'Não foi possível liberar o cadastro. Confira sua conexão e tente novamente.';
                if (button) button.textContent = 'TENTAR NOVAMENTE';
            } finally {
                this.confirmingVictory = false;
                if (button) button.disabled = false;
            }
        }

        restart() {
            this.recipeIdx = 0;
            this.taskIdx = 0;
            this.score = 0;
            this.mistakes = 0;
            this.recipes = generateDynamicRecipes();

            const scoreEl = document.getElementById('score-val');
            if (scoreEl) scoreEl.textContent = '0';

            this.view3D.resetIngredients();

            const victoryScreen = document.getElementById('screen-victory');
            if (victoryScreen) victoryScreen.style.display = 'none';

            const hud = document.getElementById('screen-hud');
            if (hud) hud.style.display = 'block';

            this.loadCurrentTask();
        }

        showToast(msg, type) {
            const el = document.getElementById('hud-toast');
            if (!el) return;
            el.textContent = msg;
            el.className = `hud-toast-banner ${type}`;
            el.style.display = 'block';
            setTimeout(() => {
                if (el.textContent === msg) el.style.display = 'none';
            }, 2200);
        }

        hideToast() {
            const el = document.getElementById('hud-toast');
            if (el) el.style.display = 'none';
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        const scene3D = new WitchScene3D();
        const gameLogic = new GameController(scene3D);
        window.gameLogic = gameLogic;
        scene3D.prepareFirstTask(gameLogic.currentTask(), () => gameLogic.prefetchNextTask());
    });

})();
