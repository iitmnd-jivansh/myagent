import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';

export class VRMController {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        
        // Camera for head/shoulders
        this.camera = new THREE.PerspectiveCamera(30, this.container.clientWidth / this.container.clientHeight, 0.1, 20.0);
        this.camera.position.set(0.0, 1.4, 1.5);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);
        
        // Light
        const light = new THREE.DirectionalLight(0xffffff, Math.PI);
        light.position.set(1.0, 1.0, 1.0).normalize();
        this.scene.add(light);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);
        
        this.vrm = null;
        this.onVRMLoaded = null;

        // Resize handling
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        });
    }

    async loadVRM(url) {
        const loader = new GLTFLoader();
        
        // Install VRM Plugin
        loader.register((parser) => {
            return new VRMLoaderPlugin(parser);
        });

        return new Promise((resolve, reject) => {
            loader.load(
                url,
                (gltf) => {
                    this.vrm = gltf.userData.vrm;
                    
                    // Put VRM in a group to force rotation, as animations can sometimes override scene rotation
                    const vrmGroup = new THREE.Group();
                    vrmGroup.rotation.y = Math.PI;
                    vrmGroup.add(this.vrm.scene);
                    this.scene.add(vrmGroup);
                    
                    // Adjust camera height based on VRM head position
                    this.vrm.scene.updateMatrixWorld(true);
                    const head = this.vrm.humanoid.getNormalizedBoneNode('head');
                    if (head) {
                        const headPos = new THREE.Vector3();
                        head.getWorldPosition(headPos);
                        this.camera.position.set(0, headPos.y, 1.5);
                        this.camera.lookAt(0, headPos.y, 0);
                    }
                    
                    if (this.onVRMLoaded) this.onVRMLoaded(this.vrm);
                    resolve(this.vrm);
                },
                (progress) => console.log('Loading VRM...', 100.0 * (progress.loaded / progress.total), '%'),
                (error) => {
                    console.error('Failed to load VRM:', error);
                    reject(error);
                }
            );
        });
    }

    update(deltaTime) {
        if (this.vrm) {
            this.vrm.update(deltaTime);
        }
        this.renderer.render(this.scene, this.camera);
    }
}
