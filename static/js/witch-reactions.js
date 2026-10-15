/**
 * witch-reactions.js
 * Controlador de Animações e Reações Procedurais da Bruxa (Three.js)
 * Compatível com o esqueleto real de 97 ossos do model.glb
 */

(function(root, factory) {
    if (typeof define === 'function' && define.amd) {
        define(['three'], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('three'));
    } else {
        root.WitchReactions = factory(root.THREE);
    }
}(typeof self !== 'undefined' ? self : this, function(THREE) {
    'use strict';

    class WitchController {
        constructor() {
            this.model = null;
            this.skeleton = null;
            this.mixer = null;
            this.actions = {};
            this.currentAction = null;

            // Mapeamento dos ossos do esqueleto
            this.bones = {
                root: null,          // spine
                spine1: null,        // spine.001
                spine2: null,        // spine.002
                chest: null,         // spine.003
                neck: null,          // spine.004
                head: null,          // spine.005
                hat: null,           // spine.006
                shoulderL: null,     // shoulder.L
                upperArmL: null,     // upper_arm.L
                forearmL: null,      // forearm.L
                handL: null,         // hand.L
                shoulderR: null,     // shoulder.L.001
                upperArmR: null,     // upper_arm.L.001
                forearmR: null,      // forearm.L.001
                handR: null          // hand.L.001
            };

            // Estado de reação procedural
            this.reaction = {
                type: null,          // 'happy' | 'disapprove' | null
                time: 0,
                duration: 1.8,
                weight: 0,
                onComplete: null
            };

            // Quaternions temporários para cálculos eficientes sem alocação
            this._qTemp = new THREE.Quaternion();
            this._euler = new THREE.Euler(0, 0, 0, 'YXZ');
            this._basePosition = new THREE.Vector3();
            this._baseRotationY = 0;
        }

        /**
         * Inicializa o controlador com o modelo carregado e suas animações
         */
        init(gltf) {
            this.model = gltf.scene;

            // Busca os ossos na hierarquia
            this.model.traverse((child) => {
                if (child.isBone) {
                    const name = child.name;
                    if (name === 'spine') this.bones.root = child;
                    else if (name === 'spine.001') this.bones.spine1 = child;
                    else if (name === 'spine.002') this.bones.spine2 = child;
                    else if (name === 'spine.003') this.bones.chest = child;
                    else if (name === 'spine.004') this.bones.neck = child;
                    else if (name === 'spine.005') this.bones.head = child;
                    else if (name === 'spine.006') this.bones.hat = child;
                    else if (name === 'shoulder.L') this.bones.shoulderL = child;
                    else if (name === 'upper_arm.L') this.bones.upperArmL = child;
                    else if (name === 'forearm.L') this.bones.forearmL = child;
                    else if (name === 'hand.L') this.bones.handL = child;
                    else if (name === 'shoulder.L.001') this.bones.shoulderR = child;
                    else if (name === 'upper_arm.L.001') this.bones.upperArmR = child;
                    else if (name === 'forearm.L.001') this.bones.forearmR = child;
                    else if (name === 'hand.L.001') this.bones.handR = child;
                }
            });

            this._basePosition.copy(this.model.position);
            this._baseRotationY = this.model.rotation.y;

            // Configura o mixer com os clipes do GLTF
            if (gltf.animations && gltf.animations.length > 0) {
                this.mixer = new THREE.AnimationMixer(this.model);
                gltf.animations.forEach((clip) => {
                    const action = this.mixer.clipAction(clip);
                    this.actions[clip.name] = action;
                });

                // Inicia idle-loop por padrão
                if (this.actions['idle-loop']) {
                    this.playIdle();
                } else if (gltf.animations[0]) {
                    this.playAction(gltf.animations[0].name);
                }
            }

            return this;
        }

        playIdle(crossFadeDuration = 0.5) {
            return this.playAction('idle-loop', crossFadeDuration);
        }

        playWalk(crossFadeDuration = 0.4) {
            return this.playAction('walk-loop', crossFadeDuration);
        }

        playAction(name, crossFadeDuration = 0.5) {
            const nextAction = this.actions[name];
            if (!nextAction) return null;

            if (this.currentAction === nextAction) {
                if (!nextAction.isRunning()) nextAction.play();
                return nextAction;
            }

            if (this.currentAction) {
                this.currentAction.fadeOut(crossFadeDuration);
            }

            nextAction.reset().fadeIn(crossFadeDuration).play();
            this.currentAction = nextAction;
            return nextAction;
        }

        /**
         * Dispara a reação de felicidade (resposta correta)
         */
        triggerHappy(duration = 2.0, onComplete = null) {
            this.reaction.type = 'happy';
            this.reaction.time = 0;
            this.reaction.duration = duration;
            this.reaction.weight = 0;
            this.reaction.onComplete = onComplete;
        }

        /**
         * Dispara a reação de desaprovação (resposta errada)
         */
        triggerDisapprove(duration = 1.6, onComplete = null) {
            this.reaction.type = 'disapprove';
            this.reaction.time = 0;
            this.reaction.duration = duration;
            this.reaction.weight = 0;
            this.reaction.onComplete = onComplete;
        }

        /**
         * Atualização por frame chamada no render loop
         * O AnimationMixer é atualizado ANTES das sobreposições procedurais
         */
        update(delta) {
            if (this.mixer) {
                this.mixer.update(delta);
            }

            // Se há reação ativa, aplica os offsets procedurais nos ossos e corpo
            if (this.reaction.type) {
                this.reaction.time += delta;
                const progress = this.reaction.time / this.reaction.duration;

                if (progress >= 1.0) {
                    const cb = this.reaction.onComplete;
                    this.reaction.type = null;
                    this.reaction.weight = 0;
                    this.reaction.time = 0;
                    // Restaura posição e rotação base
                    this.model.position.copy(this._basePosition);
                    this.model.rotation.y = this._baseRotationY;
                    if (cb) cb();
                } else {
                    // Curva de peso suave (fade-in -> ápice -> fade-out)
                    let w = 0;
                    if (progress < 0.2) {
                        w = progress / 0.2;
                    } else if (progress < 0.65) {
                        w = 1.0;
                    } else {
                        w = 1.0 - (progress - 0.65) / 0.35;
                    }
                    this.reaction.weight = THREE.MathUtils.clamp(w, 0, 1);

                    if (this.reaction.type === 'happy') {
                        this._applyHappy(progress, this.reaction.weight);
                    } else if (this.reaction.type === 'disapprove') {
                        this._applyDisapprove(progress, this.reaction.weight);
                    }
                }
            }
        }

        /**
         * Reação Happy: braços levantados em comemoração, peito erguido, cabeça animada e pulo alegre
         */
        _applyHappy(progress, weight) {
            const time = this.reaction.time * 7.0;
            const bounce = Math.abs(Math.sin(time)) * 0.14 * weight;

            // Movimento vertical alegre do corpo inteiro
            this.model.position.y = this._basePosition.y + bounce;
            this.model.rotation.y = this._baseRotationY + Math.sin(time * 0.5) * 0.08 * weight;

            // Cabeça inclinada alegremente para cima com leve balanço lateral
            if (this.bones.head) {
                const nod = -0.4 * weight + Math.sin(time * 0.8) * 0.1 * weight;
                const tilt = Math.cos(time * 0.6) * 0.15 * weight;
                this._euler.set(nod, tilt, 0, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.head.quaternion.multiply(this._qTemp);
            }

            // Coluna/peito arqueado com energia
            if (this.bones.chest) {
                this._euler.set(-0.2 * weight, 0, 0, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.chest.quaternion.multiply(this._qTemp);
            }

            // Braço Esquerdo levantado em vitória
            if (this.bones.upperArmL) {
                const armWave = Math.sin(time) * 0.2 * weight;
                this._euler.set(0, 0.4 * weight, 1.35 * weight + armWave, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.upperArmL.quaternion.multiply(this._qTemp);
            }
            if (this.bones.forearmL) {
                this._euler.set(0, 0, 0.7 * weight, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.forearmL.quaternion.multiply(this._qTemp);
            }

            // Braço Direito levantado em vitória (espelhado)
            if (this.bones.upperArmR) {
                const armWave = Math.cos(time) * 0.2 * weight;
                this._euler.set(0, -0.4 * weight, -1.35 * weight - armWave, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.upperArmR.quaternion.multiply(this._qTemp);
            }
            if (this.bones.forearmR) {
                this._euler.set(0, 0, -0.7 * weight, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.forearmR.quaternion.multiply(this._qTemp);
            }
        }

        /**
         * Reação Disapprove: recuo corporal claro, cabeça balançando em "não, não" e postura decepcionada
         */
        _applyDisapprove(progress, weight) {
            const time = this.reaction.time * 12.0;
            // Movimento senoidal rápido e enfático de negação
            const headShake = Math.sin(time) * 0.45 * weight;

            // Recuo corporal sutil para trás e leve giro de desagrado
            this.model.position.z = this._basePosition.z - 0.12 * weight;
            this.model.position.y = this._basePosition.y - 0.04 * weight;
            this.model.rotation.y = this._baseRotationY + headShake * 0.2;

            // Cabeça balançando claramente em "não" e levemente abaixada
            if (this.bones.head) {
                // Rotação nos eixos Y e Z do esqueleto para garantir movimento nítido
                this._euler.set(0.25 * weight, headShake, headShake * 0.35, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.head.quaternion.multiply(this._qTemp);
            }

            // Coluna curvada para a frente em desapontamento
            if (this.bones.chest) {
                this._euler.set(0.25 * weight, headShake * 0.2, 0, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.chest.quaternion.multiply(this._qTemp);
            }

            // Braços caídos para baixo e ombros recolhidos
            if (this.bones.upperArmL) {
                this._euler.set(0.2 * weight, 0, -0.4 * weight, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.upperArmL.quaternion.multiply(this._qTemp);
            }
            if (this.bones.upperArmR) {
                this._euler.set(0.2 * weight, 0, 0.4 * weight, 'YXZ');
                this._qTemp.setFromEuler(this._euler);
                this.bones.upperArmR.quaternion.multiply(this._qTemp);
            }
        }
    }

    return WitchController;
}));
