import React from 'react';
import {createRoot} from 'react-dom/client';
import {Scene, BoxGeometry, InstancedMesh, MeshBasicMaterial} from 'three';
const scene = new Scene();
scene.add(new InstancedMesh(new BoxGeometry(1,1,1),new MeshBasicMaterial(),2));
createRoot(document.getElementById('root')!).render(<main>Dependency probe: {scene.children.length}</main>);
