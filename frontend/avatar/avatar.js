import * as THREE from 'three';
import { VRMController } from './vrmController.js';
import { AnimationManager } from './animations.js';
import { LipSync } from './lipSync.js';

class AvatarAPI {
    constructor() {
        this.vrmController = null;
        this.animationManager = null;
        this.lipSync = null;
        this.clock = new THREE.Clock();
        this.isPaused = false;
        this.requestAnimationFrameId = null;
        this.analyzerData = null;
    }

    init(containerId) {
        this.vrmController = new VRMController(containerId);
        this.animationManager = new AnimationManager();
        this.lipSync = new LipSync();

        this.vrmController.onVRMLoaded = (vrm) => {
            this.animationManager.setup(vrm);
            this.lipSync.setup(vrm);
        };

        this._renderLoop();
    }

    async load(vrmUrl, idleVrmaUrl = null, talkVrmaUrl = null) {
        if (!this.vrmController) throw new Error("Avatar not initialized. Call init() first.");
        
        const vrm = await this.vrmController.loadVRM(vrmUrl);
        await this.animationManager.loadAnimations(vrm, idleVrmaUrl, talkVrmaUrl);
        return vrm;
    }

    startSpeaking() {
        if (this.animationManager) this.animationManager.startTalking();
        if (this.lipSync) this.lipSync.start();
    }

    stopSpeaking() {
        if (this.animationManager) this.animationManager.stopTalking();
        if (this.lipSync) this.lipSync.stop();
    }

    pause() {
        this.isPaused = true;
    }

    resume() {
        this.isPaused = false;
        this.clock.getDelta(); // Clear accumulated time
    }

    setAnalyzerData(dataArray) {
        this.analyzerData = dataArray;
    }

    _renderLoop() {
        this.requestAnimationFrameId = requestAnimationFrame(() => this._renderLoop());

        if (this.isPaused) return;

        const deltaTime = this.clock.getDelta();

        if (this.lipSync && this.analyzerData) {
            this.lipSync.update(this.analyzerData);
        }

        if (this.animationManager) {
            this.animationManager.update(deltaTime);
        }

        if (this.vrmController) {
            this.vrmController.update(deltaTime);
        }
    }
}

// Export as a singleton and attach to window
export const avatar = new AvatarAPI();
window.avatar = avatar;
