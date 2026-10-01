'use strict';

// Visor WebGL autocontenido. Toda coordenada interna procede del modelo de simulación.
(() => {
  const ID = () => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  function multiply(a, b) {
    const out = new Array(16).fill(0);
    for (let column = 0; column < 4; column++) for (let row = 0; row < 4; row++)
      for (let inner = 0; inner < 4; inner++) out[column * 4 + row] += a[inner * 4 + row] * b[column * 4 + inner];
    return out;
  }
  const translate = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];
  const scale = (x, y, z) => [x, 0, 0, 0, 0, y, 0, 0, 0, 0, z, 0, 0, 0, 0, 1];
  const rotateZ = (a) => [Math.cos(a), Math.sin(a), 0, 0, -Math.sin(a), Math.cos(a), 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const rotateY = (a) => [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1];
  const rotateX = (a) => [1, 0, 0, 0, 0, Math.cos(a), Math.sin(a), 0, 0, -Math.sin(a), Math.cos(a), 0, 0, 0, 0, 1];
  function perspective(aspect) {
    const f = 1 / Math.tan(Math.PI / 6), near = 5, far = 4000;
    return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0];
  }
  function normalize(v) { const n = Math.hypot(...v) || 1; return v.map((x) => x / n); }
  function lookAt(eye, target) {
    const z = normalize(eye.map((v, i) => v - target[i]));
    const x = normalize([z[2], 0, -z[0]]), y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
      -x.reduce((s, v, i) => s + v * eye[i], 0), -y.reduce((s, v, i) => s + v * eye[i], 0), -z.reduce((s, v, i) => s + v * eye[i], 0), 1];
  }
  function transform(m, v) { return [0, 1, 2, 3].map((row) => m[row] * v[0] + m[4 + row] * v[1] + m[8 + row] * v[2] + m[12 + row] * v[3]); }
  function shader(gl, type, source) {
    const result = gl.createShader(type); gl.shaderSource(result, source); gl.compileShader(result);
    if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(result));
    return result;
  }
  function program(gl) {
    const vert = shader(gl, gl.VERTEX_SHADER, `attribute vec3 position; attribute vec3 normal;
      uniform mat4 matrix; uniform mat4 modelView; varying float shade;
      void main(){gl_Position=matrix*vec4(position,1.0);vec3 n=normalize((modelView*vec4(normal,0.0)).xyz);
      shade=0.58+0.42*max(dot(n,normalize(vec3(0.45,0.75,0.7))),0.0);}`);
    const frag = shader(gl, gl.FRAGMENT_SHADER, `precision mediump float; uniform vec4 color; varying float shade;
      void main(){gl_FragColor=vec4(color.rgb*shade,color.a);}`);
    const result = gl.createProgram(); gl.attachShader(result, vert); gl.attachShader(result, frag); gl.linkProgram(result);
    if (!gl.getProgramParameter(result, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(result));
    return result;
  }
  function box() {
    const vertices = [], faces = [
      [[0, 0, 1], [[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]]],
      [[0, 0, -1], [[1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1]]],
      [[1, 0, 0], [[1, -1, 1], [1, -1, -1], [1, 1, -1], [1, 1, 1]]],
      [[-1, 0, 0], [[-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]]],
      [[0, 1, 0], [[-1, 1, 1], [1, 1, 1], [1, 1, -1], [-1, 1, -1]]],
      [[0, -1, 0], [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]]],
    ];
    for (const [normal, points] of faces) for (const index of [0, 1, 2, 0, 2, 3]) vertices.push(...points[index].map((v) => v / 2), ...normal);
    return new Float32Array(vertices);
  }
  function cylinder() {
    const vertices = [], segments = 16;
    for (let i = 0; i < segments; i++) {
      const a = i * 2 * Math.PI / segments, b = (i + 1) * 2 * Math.PI / segments;
      const p = [Math.cos(a) / 2, Math.sin(a) / 2], q = [Math.cos(b) / 2, Math.sin(b) / 2];
      const side = [[p[0], -.5, p[1]], [q[0], -.5, q[1]], [q[0], .5, q[1]], [p[0], .5, p[1]]];
      for (const j of [0, 1, 2, 0, 2, 3]) { const point = side[j]; vertices.push(...point, point[0] * 2, 0, point[2] * 2); }
      for (const y of [-.5, .5]) {
        for (const point of [[0, y, 0], [p[0], y, p[1]], [q[0], y, q[1]]]) vertices.push(...point, 0, y < 0 ? -1 : 1, 0);
      }
    }
    return new Float32Array(vertices);
  }
  const palette = {
    body: [0.13, .18, .29], cover: [.70, .77, .82], tray: [.56, .66, .72],
    assembly: [.57, .68, .78], panel: [.12, .37, .57], roller: [.18, .23, .31],
    screw: [.74, .76, .78], guide: [.31, .54, .66], hinge: [.48, .57, .62],
    pcb: [.07, .38, .33], motor: [.35, .43, .50], connector: [.19, .39, .58], cable: [.30, .44, .60],
  };

  class Viewer {
    constructor(canvas, model, options = {}) {
      this.canvas = canvas; this.model = model; this.overlay = !!options.overlay;
      this.gl = canvas.getContext('webgl', {alpha: true, antialias: true});
      if (!this.gl) throw new Error('WebGL no disponible');
      const gl = this.gl; this.program = program(gl); gl.useProgram(this.program);
      this.position = gl.getAttribLocation(this.program, 'position'); this.normal = gl.getAttribLocation(this.program, 'normal');
      this.matrix = gl.getUniformLocation(this.program, 'matrix'); this.modelView = gl.getUniformLocation(this.program, 'modelView'); this.color = gl.getUniformLocation(this.program, 'color');
      this.meshes = {};
      for (const [name, vertices] of Object.entries({box: box(), cylinder: cylinder()})) {
        const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
        this.meshes[name] = {buffer, count: vertices.length / 6};
      }
      gl.enable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      this.azimuth = .78; this.elevation = .34; this.radius = this.overlay ? 340 : 1050;
      this.state = null; this.selected = null; this.exploded = false; this.explosionLevel = 0; this.hideCovers = false;
      this.stepAnimation = null; this.stepAnimationLevel = 0;
      this.corrections = []; this.onSelect = options.onSelect || (() => {}); this.animationStart = 0;
      if (!this.overlay) this.controls();
      new ResizeObserver(() => this.render()).observe(canvas);
      this.render();
    }

    controls() {
      let pointer = null, moved = false, pinch = null;
      this.canvas.addEventListener('pointerdown', (event) => { pointer = [event.clientX, event.clientY]; moved = false; this.canvas.setPointerCapture(event.pointerId); });
      this.canvas.addEventListener('pointermove', (event) => {
        if (!pointer) return;
        const dx = event.clientX - pointer[0], dy = event.clientY - pointer[1];
        if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
        this.azimuth += dx * .008; this.elevation = Math.max(-1.2, Math.min(1.2, this.elevation + dy * .006));
        pointer = [event.clientX, event.clientY]; this.render();
      });
      this.canvas.addEventListener('pointerup', (event) => { if (!moved) this.pick(event); pointer = null; });
      this.canvas.addEventListener('wheel', (event) => { event.preventDefault(); this.radius = Math.max(350, Math.min(2200, this.radius * Math.exp(event.deltaY * .001))); this.render(); }, {passive: false});
      this.canvas.addEventListener('touchmove', (event) => {
        if (event.touches.length !== 2) { pinch = null; return; }
        const distance = Math.hypot(event.touches[0].clientX - event.touches[1].clientX, event.touches[0].clientY - event.touches[1].clientY);
        if (pinch) { this.radius = Math.max(350, Math.min(2200, this.radius * pinch / distance)); this.render(); }
        pinch = distance;
      }, {passive: true});
      this.canvas.addEventListener('touchend', () => { pinch = null; });
    }

    correction(component) {
      return this.corrections.find((item) => item.component_id === component.id && item.state_id === this.state?.id);
    }

    geometry(component) {
      const geometry = component.geometry, correction = this.correction(component);
      const factor = correction?.scale || 1, offset = correction?.offset_mm || [0, 0, 0];
      const position = geometry.position_mm.map((v, i) => v + offset[i]);
      if (this.explosionLevel) {
        const direction = component.explosion?.direction || [0, 0, 0];
        const distance = component.explosion?.distance_mm || 0;
        direction.forEach((value, i) => { position[i] += value * distance * this.explosionLevel; });
      }
      if (this.stepAnimation && this.stepAnimation.component_id === component.id) {
        this.stepAnimation.direction.forEach((value, i) => {
          position[i] += value * this.stepAnimation.distance_mm * this.stepAnimationLevel;
        });
      }
      return {position, size: geometry.size_mm.map((v) => v * factor), rotation: correction?.rotation_deg || [0, 0, 0]};
    }

    visible(component) {
      if (!component.geometry) return false;
      if (this.hideCovers && (component.category === 'cover' || component.id === 'body')) return false;
      if (this.state?.removed_components?.includes(component.id)) return false;
      let parent = component.parent_id;
      while (parent) {
        if (this.state?.removed_components?.includes(parent)) return false;
        parent = this.model.components.find((item) => item.id === parent)?.parent_id;
      }
      if (this.overlay) {
        const selected = this.model.components.find((item) => item.id === this.selected);
        if (!selected) return false;
        if (component.id !== selected.id && component.parent_id !== selected.id) return false;
      }
      return true;
    }

    cameraMatrices() {
      const target = this.overlay ? this.model.components.find((c) => c.id === this.selected)?.geometry?.position_mm || [0, 260, 0] : [0, 225, 0];
      const eye = [target[0] + Math.sin(this.azimuth) * Math.cos(this.elevation) * this.radius,
        target[1] + Math.sin(this.elevation) * this.radius,
        target[2] + Math.cos(this.azimuth) * Math.cos(this.elevation) * this.radius];
      const rect = this.canvas.getBoundingClientRect(); return {view: lookAt(eye, target), projection: perspective(Math.max(rect.width, 1) / Math.max(rect.height, 1))};
    }

    render() {
      const gl = this.gl, canvas = this.canvas, rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.round(rect.width * pixelRatio), height = Math.round(rect.height * pixelRatio);
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      gl.viewport(0, 0, width, height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      const {view, projection} = this.cameraMatrices(); this.lastCamera = {view, projection};
      const parts = this.model.components.filter((item) => this.visible(item));
      for (const component of parts) {
        const {position, size, rotation} = this.geometry(component), cylindrical = component.geometry.primitive === 'cylinder';
        let local = cylindrical ? multiply(rotateZ(Math.PI / 2), scale(size[1], size[0], size[2])) : scale(...size);
        const radians = rotation.map((value) => value * Math.PI / 180);
        local = multiply(multiply(multiply(rotateZ(radians[2]), rotateY(radians[1])), rotateX(radians[0])), local);
        if (this.stepAnimation?.component_id === component.id) {
          if (this.stepAnimation.animation_type === 'UNSCREW') local = multiply(rotateY(this.stepAnimationLevel * Math.PI * 2), local);
          if (this.stepAnimation.animation_type === 'ROTATE_OPEN') local = multiply(rotateZ(this.stepAnimationLevel * .35), local);
        }
        const matrix = multiply(translate(...position), local);
        const modelView = multiply(view, matrix), projected = multiply(projection, modelView);
        const selected = component.id === this.selected || component.parent_id === this.selected;
        const rgb = selected ? [0.91, .25, .11] : palette[component.category] || [.54, .64, .72];
        const alpha = this.overlay ? .77 : selected ? .88 : 1;
        gl.uniformMatrix4fv(this.matrix, false, new Float32Array(projected));
        gl.uniformMatrix4fv(this.modelView, false, new Float32Array(modelView));
        gl.uniform4f(this.color, ...rgb, alpha);
        const mesh = this.meshes[component.geometry.primitive] || this.meshes.box;
        gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buffer);
        gl.enableVertexAttribArray(this.position); gl.vertexAttribPointer(this.position, 3, gl.FLOAT, false, 24, 0);
        gl.enableVertexAttribArray(this.normal); gl.vertexAttribPointer(this.normal, 3, gl.FLOAT, false, 24, 12);
        gl.drawArrays(gl.TRIANGLES, 0, mesh.count);
      }
    }

    pick(event) {
      const rect = this.canvas.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      const {view, projection} = this.lastCamera || this.cameraMatrices();
      let winner = null, distance = 48;
      for (const part of this.model.components.filter((item) => this.visible(item))) {
        const p = transform(multiply(projection, view), [...this.geometry(part).position, 1]);
        if (p[3] <= 0) continue;
        const px = (p[0] / p[3] + 1) * rect.width / 2, py = (1 - p[1] / p[3]) * rect.height / 2;
        const d = Math.hypot(x - px, y - py);
        if (d < distance) { winner = part; distance = d; }
      }
      if (winner) { this.selected = winner.id; this.onSelect(winner); this.render(); }
    }

    setState(state) { this.state = state; this.render(); }
    setSelected(id) {
      this.selected = id;
      if (this.overlay) {
        const component = this.model.components.find((item) => item.id === id);
        const maximum = Math.max(...(component?.geometry?.size_mm || [170]));
        this.radius = Math.max(90, Math.min(650, maximum * 2.7));
      }
      this.render();
    }
    setExploded(value) {
      this.exploded = value; const start = performance.now(), initial = this.explosionLevel, target = value ? 1 : 0;
      const animate = () => {
        const t = Math.min(1, (performance.now() - start) / 700), eased = t * t * (3 - 2 * t);
        this.explosionLevel = initial + (target - initial) * eased; this.render();
        if (t < 1) requestAnimationFrame(animate);
      };
      animate();
    }
    animateStep(animation) {
      this.stepAnimation = animation; const start = performance.now();
      const animate = () => {
        const t = Math.min(1, (performance.now() - start) / 1100);
        this.stepAnimationLevel = Math.sin(Math.PI * t) * .65; this.render();
        if (t < 1) requestAnimationFrame(animate);
        else { this.stepAnimationLevel = 0; this.render(); }
      };
      animate();
    }
    setHideCovers(value) { this.hideCovers = value; this.render(); }
    setCorrections(items) { this.corrections = items; this.render(); }
  }

  window.DSTwin = {Viewer};
})();
