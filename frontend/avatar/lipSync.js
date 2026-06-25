export class LipSync {
    constructor() {
        this.vrm = null;
        this.isSpeaking = false;
    }

    setup(vrm) {
        this.vrm = vrm;
    }

    start() {
        this.isSpeaking = true;
    }

    stop() {
        this.isSpeaking = false;
        if (this.vrm && this.vrm.expressionManager) {
            this.vrm.expressionManager.setValue('aa', 0);
        }
    }

    update(analyzerData) {
        if (!this.isSpeaking || !this.vrm || !this.vrm.expressionManager || !analyzerData) return;

        // Calculate average volume from frequency data
        let sum = 0;
        const length = analyzerData.length || 1;
        for (let i = 0; i < length; i++) {
            sum += analyzerData[i];
        }
        const average = sum / length;
        
        // Normalize volume to 0-1 (assuming max value 255)
        // Multiply by a factor to make it more responsive to speech
        let volume = (average / 255.0) * 2.0;
        volume = Math.max(0.0, Math.min(1.0, volume));
        
        // Use 'aa' expression for basic lip sync as requested
        this.vrm.expressionManager.setValue('aa', volume);
    }
}
