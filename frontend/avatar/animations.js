import * as THREE from 'three';
import { VRMAnimationLoaderPlugin } from '@pixiv/three-vrm-animation';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class AnimationManager {
    constructor() {
        this.mixer = null;
        this.idleAction = null;
        this.talkAction = null;
        this.currentAction = null;
    }

    setup(vrm) {
        this.mixer = new THREE.AnimationMixer(vrm.scene);
    }

    async loadAnimations(vrm, idleUrl, talkUrl) {
        const loader = new GLTFLoader();
        loader.register((parser) => new VRMAnimationLoaderPlugin(parser));

        try {
            const [idleGltf, talkGltf] = await Promise.all([
                this._loadAnimation(loader, idleUrl),
                this._loadAnimation(loader, talkUrl)
            ]);

            if (idleGltf && idleGltf.userData.vrmAnimations && idleGltf.userData.vrmAnimations.length > 0) {
                const idleClip = idleGltf.userData.vrmAnimations[0].createAnimationClip(vrm);
                this.idleAction = this.mixer.clipAction(idleClip);
                this.idleAction.setEffectiveWeight(1.0);
                this.idleAction.play();
                this.currentAction = this.idleAction;
            } else {
                console.warn("Idle animation not found or empty.");
            }

            if (talkGltf && talkGltf.userData.vrmAnimations && talkGltf.userData.vrmAnimations.length > 0) {
                const talkClip = talkGltf.userData.vrmAnimations[0].createAnimationClip(vrm);
                this.talkAction = this.mixer.clipAction(talkClip);
            } else {
                console.warn("Talk animation not found or empty.");
            }
        } catch (error) {
            console.error('Failed to load animations:', error);
        }
    }

    _loadAnimation(loader, url) {
        if (!url) return Promise.resolve(null);
        return new Promise((resolve) => {
            loader.load(
                url, 
                resolve, 
                undefined, 
                (err) => {
                    console.warn(`Could not load animation at ${url}`, err);
                    resolve(null);
                }
            );
        });
    }

    startTalking() {
        if (this.talkAction && this.idleAction) {
            this.talkAction.reset();
            this.talkAction.setEffectiveWeight(1.0);
            this.talkAction.play();
            this.talkAction.crossFadeFrom(this.idleAction, 0.5, true);
            this.currentAction = this.talkAction;
        }
    }

    stopTalking() {
        if (this.idleAction && this.talkAction && this.currentAction === this.talkAction) {
            this.idleAction.reset();
            this.idleAction.setEffectiveWeight(1.0);
            this.idleAction.play();
            this.idleAction.crossFadeFrom(this.talkAction, 0.5, true);
            this.currentAction = this.idleAction;
        }
    }

    update(deltaTime) {
        if (this.mixer) {
            this.mixer.update(deltaTime);
        }
    }
}
