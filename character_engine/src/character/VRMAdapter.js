import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { VRMAnimationLoaderPlugin, createVRMAnimationClip } from '@pixiv/three-vrm-animation';
import { Logger } from '../logger.js';

/**
 * VRMAdapter - model-agnostic wrapper around any VRM model.
 * Detects capabilities, supports VRMA playback, and exposes a unified API.
 */
export class VRMAdapter {
  constructor() {
    this.vrm = null;
    this.scene = null;
    this.mixer = null;
    this._clipCache = new Map();
    this._currentAction = null;
    this.capabilities = {
      humanoid: false,
      expressions: false,
      lookAt: false,
      springBones: false,
    };
    this._expressionNames = [];
    this._boneCache = {};
  }

  get loaded() { return this.vrm !== null; }

  async load(modelPath) {
    return new Promise((resolve, reject) => {
      try {
        const loader = new GLTFLoader();
        loader.register((parser) => new VRMLoaderPlugin(parser));

        loader.load(
          modelPath,
          (gltf) => {
            try {
              this.vrm = gltf.userData.vrm;
              this.scene = this.vrm.scene;

              // Detect capabilities
              this._detectCapabilities();

              // Cache initial hips Y rest height to prevent pelvis sinking
              const hips = this.getBone('hips');
              this.initialHipsY = (hips && hips.position && hips.position.y > 0.3) ? hips.position.y : 0.8801;

              // Default pose: lower arms from T-pose
              this._setDefaultPose();

              // Face camera
              this.scene.rotation.y = Math.PI;

              // Initialize AnimationMixer for VRMA clips
              this.mixer = new THREE.AnimationMixer(this.scene);

              Logger.info('VRM loaded:', modelPath);
              Logger.info('Capabilities:', JSON.stringify(this.capabilities));
              resolve(this);
            } catch (err) {
              Logger.error('VRM post-load error:', err);
              reject(err);
            }
          },
          undefined,
          (error) => {
            Logger.error('VRM load error:', error);
            reject(error);
          }
        );
      } catch (err) {
        Logger.error('VRM loader setup error:', err);
        reject(err);
      }
    });
  }

  _detectCapabilities() {
    try {
      this.capabilities.humanoid = !!this.vrm.humanoid;
      this.capabilities.lookAt = !!this.vrm.lookAt;
      this.capabilities.springBones = !!this.vrm.springBoneManager;

      if (this.vrm.expressionManager) {
        this.capabilities.expressions = true;
        this._expressionNames = this.vrm.expressionManager.expressions.map(e => e.expressionName);
        Logger.info('Available expressions:', this._expressionNames.join(', '));
      }
    } catch (e) {
      Logger.warn('Capability detection partial failure:', e);
    }
  }

  _setDefaultPose() {
    if (!this.capabilities.humanoid) return;
    try {
      const leftArm = this.getBone('leftUpperArm');
      const rightArm = this.getBone('rightUpperArm');
      const leftLower = this.getBone('leftLowerArm');
      const rightLower = this.getBone('rightLowerArm');

      // Natural feminine relaxed resting pose (~74 deg down, slightly forward)
      if (leftArm) {
        leftArm.rotation.set(0.12, 0.05, 1.28);
      }
      if (rightArm) {
        rightArm.rotation.set(0.12, -0.05, -1.28);
      }
      if (leftLower) {
        leftLower.rotation.set(0.10, 0, 0.15);
      }
      if (rightLower) {
        rightLower.rotation.set(0.10, 0, -0.15);
      }
    } catch (e) {
      Logger.warn('Could not set default pose:', e);
    }
  }

  getBone(name) {
    if (!this.capabilities.humanoid) return null;
    if (this._boneCache[name]) return this._boneCache[name];
    try {
      const bone = this.vrm.humanoid.getNormalizedBoneNode(name);
      if (bone) this._boneCache[name] = bone;
      return bone;
    } catch (e) {
      return null;
    }
  }

  setExpression(name, value) {
    if (!this.capabilities.expressions) return;
    try {
      this.vrm.expressionManager.setValue(name, value);
    } catch (e) { /* graceful */ }
  }

  resetExpressions() {
    if (!this.capabilities.expressions) return;
    try {
      for (const name of this._expressionNames) {
        this.vrm.expressionManager.setValue(name, 0);
      }
    } catch (e) { /* graceful */ }
  }

  getExpressionNames() {
    return [...this._expressionNames];
  }

  hasExpression(name) {
    return this._expressionNames.includes(name);
  }

  setLookAt(target) {
    if (!this.capabilities.lookAt) return;
    try {
      this.vrm.lookAt.target = target;
    } catch (e) { /* graceful */ }
  }

  /**
   * Loads a .vrma animation file and retargets it to this VRM model.
   * Results are cached by vrmaPath.
   */
  async loadVRMA(vrmaPath) {
    if (!this.loaded || !this.vrm) return null;
    if (this._clipCache.has(vrmaPath)) {
      return this._clipCache.get(vrmaPath);
    }

    return new Promise((resolve) => {
      try {
        const loader = new GLTFLoader();
        loader.register((parser) => new VRMAnimationLoaderPlugin(parser));

        loader.load(
          vrmaPath,
          (gltf) => {
            try {
              const vrmAnimation = gltf.userData.vrmAnimation;
              if (!vrmAnimation) {
                Logger.warn('[VRMA] No vrmAnimation found in:', vrmaPath);
                resolve(null);
                return;
              }

              const clip = createVRMAnimationClip(vrmAnimation, this.vrm);
              this._clipCache.set(vrmaPath, clip);
              resolve(clip);
            } catch (err) {
              Logger.warn('[VRMA] Clip retarget error for', vrmaPath, err);
              resolve(null);
            }
          },
          undefined,
          (err) => {
            Logger.warn('[VRMA] Failed to load:', vrmaPath, err);
            resolve(null);
          }
        );
      } catch (e) {
        Logger.warn('[VRMA] Loader setup error:', e);
        resolve(null);
      }
    });
  }

  /**
   * Plays an AnimationClip on the VRM model via AnimationMixer with crossfading.
   */
  playVRMA(clip, loop = true, blendDuration = 0.4) {
    if (!this.mixer || !clip) return null;

    try {
      const prevAction = this._currentAction;
      const nextAction = this.mixer.clipAction(clip);

      nextAction.reset();
      nextAction.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce);
      nextAction.clampWhenFinished = !loop;

      if (prevAction && prevAction !== nextAction) {
        prevAction.fadeOut(blendDuration);
      }

      nextAction.fadeIn(blendDuration).play();
      this._currentAction = nextAction;
      return nextAction;
    } catch (e) {
      Logger.warn('[VRMA] Playback error:', e);
      return null;
    }
  }

  /**
   * Stops active VRMA action with smooth crossfade to rest.
   */
  stopVRMA(blendDuration = 0.4) {
    if (this._currentAction) {
      this._currentAction.fadeOut(blendDuration);
      this._currentAction = null;
    }
  }

  /**
   * Updates AnimationMixer for active VRMA animation tracks.
   */
  updateMixer(delta) {
    if (this.mixer) {
      try {
        this.mixer.update(delta);
      } catch (e) {
        Logger.warn('[VRMA] Mixer update error:', e);
      }
    }
  }

  update(delta) {
    if (!this.vrm) return;
    try {
      this.vrm.update(delta);
    } catch (e) {
      Logger.error('VRM update error:', e);
    }
  }

  dispose() {
    if (this.vrm) {
      try {
        if (this.scene && this.scene.parent) {
          this.scene.parent.remove(this.scene);
        }
        // Dispose textures and geometry
        this.scene?.traverse((obj) => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) {
            if (Array.isArray(obj.material)) {
              obj.material.forEach(m => m.dispose());
            } else {
              obj.material.dispose();
            }
          }
        });
      } catch (e) {
        Logger.warn('VRM dispose error:', e);
      }
      this.vrm = null;
      this.scene = null;
      this._boneCache = {};
    }
  }
}
