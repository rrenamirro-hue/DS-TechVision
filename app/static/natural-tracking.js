(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DSNaturalTracking = api;
}(typeof self !== 'undefined' ? self : this, function (root) {
  'use strict';
  const MAX_FRAME_WIDTH = 480, MAX_FRAME_HEIGHT = 360;
  const U_MAX = new Int32Array([15,15,15,15,14,14,14,13,13,12,11,10,9,8,6,3,0]);
  function orientation(image, px, py) {
    const source = image.data, stride = image.cols, center = py * stride + px;
    let m01 = 0, m10 = 0;
    for (let u = -15; u <= 15; u++) m10 += u * source[center + u];
    for (let v = 1; v <= 15; v++) {
      let sum = 0;
      for (let u = -U_MAX[v]; u <= U_MAX[v]; u++) {
        const plus = source[center + u + v * stride], minus = source[center + u - v * stride];
        sum += plus - minus; m10 += u * (plus + minus);
      }
      m01 += v * sum;
    }
    return Math.atan2(m01, m10);
  }
  function popcount(value) {
    value -= (value >>> 1) & 0x55555555;
    value = (value & 0x33333333) + ((value >>> 2) & 0x33333333);
    return (((value + (value >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
  }
  function project(matrix, x, y) {
    const z = matrix[6] * x + matrix[7] * y + matrix[8];
    if (!Number.isFinite(z) || Math.abs(z) < 1e-8) return null;
    return {x: (matrix[0] * x + matrix[1] * y + matrix[2]) / z,
      y: (matrix[3] * x + matrix[4] * y + matrix[5]) / z};
  }
  function polygonArea(points) {
    return Math.abs(points.reduce((sum, point, index) => {
      const next = points[(index + 1) % points.length]; return sum + point.x * next.y - next.x * point.y;
    }, 0)) / 2;
  }
  function featureSet(imageData, maxPoints = 350) {
    const jsfeat = root.jsfeat, {width, height} = imageData;
    const gray = new jsfeat.matrix_t(width, height, jsfeat.U8C1_t);
    const smooth = new jsfeat.matrix_t(width, height, jsfeat.U8C1_t);
    jsfeat.imgproc.grayscale(imageData.data, width, height, gray);
    jsfeat.imgproc.gaussian_blur(gray, smooth, 3, 0);
    const points = Array.from({length: Math.ceil(width * height / 3)}, () => new jsfeat.keypoint_t(0, 0, 0, 0));
    jsfeat.yape06.laplacian_threshold = 30; jsfeat.yape06.min_eigen_value_threshold = 25;
    const count = jsfeat.yape06.detect(smooth, points, 17);
    points.length = count;
    points.sort((a, b) => b.score - a.score); points.length = Math.min(count, maxPoints);
    for (const point of points) point.angle = orientation(smooth, point.x, point.y);
    const descriptors = new jsfeat.matrix_t(32, points.length, jsfeat.U8C1_t);
    if (points.length) jsfeat.orb.describe(smooth, points, points.length, descriptors);
    return {points, descriptors};
  }
  function matchDescriptors(frame, reference) {
    const query = frame.descriptors.buffer.i32, train = reference.descriptors.buffer.i32;
    const matches = [], occupied = new Map();
    for (let q = 0; q < frame.points.length; q++) {
      let best = 257, second = 257, bestIndex = -1;
      for (let t = 0; t < reference.points.length; t++) {
        let distance = 0;
        for (let word = 0; word < 8; word++) distance += popcount(query[q * 8 + word] ^ train[t * 8 + word]);
        if (distance < best) { second = best; best = distance; bestIndex = t; }
        else if (distance < second) second = distance;
      }
      if (bestIndex < 0 || best > 85 || best >= second * .82) continue;
      const previous = occupied.get(bestIndex);
      if (!previous || best < previous.distance) occupied.set(bestIndex, {query: q, train: bestIndex, distance: best});
    }
    occupied.forEach((value) => matches.push(value));
    return matches;
  }
  function estimate(reference, frame, matches, frameWidth, frameHeight) {
    if (matches.length < 9) return null;
    const jsfeat = root.jsfeat, from = [], to = [];
    for (const match of matches) {
      from.push(reference.features.points[match.train]); to.push(frame.points[match.query]);
    }
    const H = new jsfeat.matrix_t(3, 3, jsfeat.F32C1_t), mask = new jsfeat.matrix_t(matches.length, 1, jsfeat.U8C1_t);
    const params = new jsfeat.ransac_params_t(4, 4, .5, .99);
    const kernel = new jsfeat.motion_model.homography2d();
    const ok = jsfeat.motion_estimator.ransac(params, kernel, from, to, matches.length, H, mask, 650);
    if (!ok) return null;
    const inliers = matches.reduce((count, _, index) => count + (mask.data[index] ? 1 : 0), 0);
    const ratio = inliers / matches.length;
    if (inliers < 9 || ratio < .28) return null;
    const goodFrom = [], goodTo = [];
    matches.forEach((_, index) => { if (mask.data[index]) { goodFrom.push(from[index]); goodTo.push(to[index]); } });
    const spreadX = Math.max(...goodFrom.map((point) => point.x)) - Math.min(...goodFrom.map((point) => point.x));
    const spreadY = Math.max(...goodFrom.map((point) => point.y)) - Math.min(...goodFrom.map((point) => point.y));
    if (spreadX < reference.width * .25 || spreadY < reference.height * .25) return null;
    if (!kernel.run(goodFrom, goodTo, H, inliers)) return null;
    const matrix = Array.from(H.data.slice(0, 9));
    const corners = [[0,0],[reference.width,0],[reference.width,reference.height],[0,reference.height]].map(([x,y]) => project(matrix,x,y));
    if (corners.some((point) => !point || !Number.isFinite(point.x + point.y))) return null;
    const area = polygonArea(corners), frameArea = frameWidth * frameHeight;
    if (area < frameArea * .025 || area > frameArea * 1.5) return null;
    const confidence = Math.min(1, inliers / 35) * .6 + Math.min(1, ratio) * .4;
    if (confidence < .35) return null;
    return {matrix, corners, inliers, matches: matches.length, confidence};
  }
  class Tracker {
    constructor(references) { this.references = references; this.ready = false; }
    async initialize() {
      if (!root.jsfeat) throw new Error('Motor de visión no disponible');
      for (const reference of this.references) {
        const image = new Image(); image.src = reference.image_url;
        await image.decode();
        const scale = Math.min(1, 480 / image.naturalWidth, 360 / image.naturalHeight);
        const width = Math.round(image.naturalWidth * scale), height = Math.round(image.naturalHeight * scale);
        reference.width = width; reference.height = height;
        const levels = [];
        for (const factor of [1, .75, .55]) {
          const levelWidth = Math.round(width * factor), levelHeight = Math.round(height * factor);
          const canvas = document.createElement('canvas'); canvas.width = levelWidth; canvas.height = levelHeight;
          const context = canvas.getContext('2d', {willReadFrequently: true}); context.drawImage(image, 0, 0, levelWidth, levelHeight);
          const features = featureSet(context.getImageData(0, 0, levelWidth, levelHeight), 220);
          levels.push({factor, features});
        }
        const total = levels.reduce((count, level) => count + level.features.points.length, 0);
        const descriptors = new root.jsfeat.matrix_t(32, total, root.jsfeat.U8C1_t), points = [];
        let offset = 0;
        for (const level of levels) {
          descriptors.data.set(level.features.descriptors.data.slice(0, level.features.points.length * 32), offset * 32);
          level.features.points.forEach((point) => points.push({x: point.x / level.factor, y: point.y / level.factor}));
          offset += level.features.points.length;
        }
        reference.features = {points, descriptors};
      }
      this.ready = true;
    }
    match(imageData, candidateIds = null) {
      if (!this.ready) return null;
      const frame = featureSet(imageData, 450);
      if (frame.points.length < 15) return null;
      const candidates = [];
      for (const reference of this.references) {
        if (candidateIds && !candidateIds.includes(reference.reference_id)) continue;
        const matches = matchDescriptors(frame, reference.features);
        const result = estimate(reference, frame, matches, imageData.width, imageData.height);
        if (result) candidates.push({...result, reference});
      }
      candidates.sort((a, b) => b.confidence - a.confidence || b.inliers - a.inliers);
      if (!candidates.length || (candidates[1] && candidates[0].confidence < candidates[1].confidence * 1.1)) return null;
      return candidates[0];
    }
  }
  return {Tracker, project, polygonArea, featureSet, matchDescriptors, estimate, MAX_FRAME_WIDTH, MAX_FRAME_HEIGHT};
}));
