import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { Logger } from '../logger.js';

/**
 * VRMAdapter - model-agnostic wrapper around any VRM model.
 * Detects capabilities and exposes a unified API.
 */
export class VRMAdapter {
  constructor() {
    this.vrm = null;
    this.scene = null;
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

              // Default pose: lower arms from T-pose
              this._setDefaultPose();

              // Apply casual anime angel styling (skirt, casual top, halo, angel wings)
              this._applyCasualAngelStyle();

              // Face camera
              this.scene.rotation.y = Math.PI;

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

  update(delta) {
    if (!this.vrm) return;
    try {
      this.vrm.update(delta);
      this._updateAngelAccessories(delta);
    } catch (e) {
      Logger.error('VRM update error:', e);
    }
  }

  _applyCasualAngelStyle() {
    try {
      // 1. Casual Outfit Styling (clean modern casual top and shorts)
      this.scene.traverse((obj) => {
        if (!obj.isMesh || !obj.material) return;
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
        for (const mat of mats) {
          const name = mat.name || '';
          if (name.includes('Onepiece_00_CLOTH_01')) {
            // Casual chic white top
            mat.map = null;
            if (mat.color) mat.color.setHex(0xfcfcfc);
            mat.needsUpdate = true;
          } else if (name.includes('Onepiece_00_CLOTH_02')) {
            // Casual dark navy under-shorts
            mat.map = null;
            if (mat.color) mat.color.setHex(0x1e222d);
            mat.needsUpdate = true;
          } else if (name.includes('Onepiece_00_CLOTH_03')) {
            // Hide swimsuit string ties completely
            mat.transparent = true;
            mat.opacity = 0;
            mat.needsUpdate = true;
          }
        }
      });

      // 2. Add casual flared pleated anime skirt attached to hips
      const hips = this.getBone('hips');
      if (hips) {
        const skirtGeo = new THREE.CylinderGeometry(0.15, 0.25, 0.24, 32, 1, true);
        const skirtMat = new THREE.MeshStandardMaterial({
          color: 0x1e222d,
          roughness: 0.7,
          metalness: 0.1,
          side: THREE.DoubleSide,
        });
        const skirt = new THREE.Mesh(skirtGeo, skirtMat);
        skirt.position.set(0, -0.05, 0);
        hips.add(skirt);
      }

      // 3. Floating Gold Halo above head (delicate, glowing)
      const head = this.getBone('head');
      if (head) {
        const haloGeo = new THREE.TorusGeometry(0.09, 0.009, 16, 48);
        const haloMat = new THREE.MeshStandardMaterial({
          color: 0xffd700,
          emissive: 0xffaa00,
          emissiveIntensity: 0.8,
          metalness: 0.9,
          roughness: 0.15,
        });
        this._halo = new THREE.Mesh(haloGeo, haloMat);
        this._halo.rotation.x = Math.PI / 2 + 0.15;
        this._halo.position.set(0, 0.26, 0.01);
        head.add(this._halo);
      }

      // 4. Feathered Angel Wings attached to upperChest on the BACK (+Z)
      const upperChest = this.getBone('upperChest') || this.getBone('chest') || this.getBone('spine');
      if (upperChest) {
        this._leftWing = this._createAngelWing(true);
        this._rightWing = this._createAngelWing(false);

        // Positioned behind shoulder blades (+Z in bone space)
        this._leftWing.position.set(-0.05, 0.06, 0.09);
        this._rightWing.position.set(0.05, 0.06, 0.09);

        this._leftWing.rotation.set(-0.1, 0.35, -0.15);
        this._rightWing.rotation.set(-0.1, -0.35, 0.15);

        upperChest.add(this._leftWing);
        upperChest.add(this._rightWing);
      }
    } catch (e) {
      Logger.warn('Could not apply casual angel style:', e);
    }
  }

  _createAngelWing(isLeft) {
    const wing = new THREE.Group();
    const wingMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xf5f8ff,
      emissiveIntensity: 0.3,
      roughness: 0.45,
      metalness: 0.1,
      side: THREE.DoubleSide,
    });

    const featherCount = 6;
    for (let i = 0; i < featherCount; i++) {
      const len = 0.11 + (featherCount - i) * 0.022;
      const width = 0.025 + (i * 0.003);
      const geo = new THREE.ConeGeometry(width, len, 8);
      geo.translate(0, len / 2, 0);
      const feather = new THREE.Mesh(geo, wingMat);

      const angle = -0.20 + (i * 0.15);
      feather.rotation.z = isLeft ? angle : -angle;
      feather.rotation.x = 0.1;
      feather.position.set(
        isLeft ? -i * 0.018 : i * 0.018,
        -i * 0.010,
        -i * 0.005
      );
      wing.add(feather);
    }
    return wing;
  }

  _updateAngelAccessories(delta) {
    this._accessoryTime = (this._accessoryTime || 0) + delta;
    if (this._halo) {
      this._halo.position.y = 0.26 + Math.sin(this._accessoryTime * 2.0) * 0.010;
      this._halo.rotation.z = Math.sin(this._accessoryTime * 1.2) * 0.04;
    }
    if (this._leftWing && this._rightWing) {
      const flutter = Math.sin(this._accessoryTime * 2.5) * 0.08;
      this._leftWing.rotation.y = 0.35 + flutter;
      this._rightWing.rotation.y = -0.35 - flutter;
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
