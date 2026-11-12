import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3-force";

const WIDTH = 1200;
const HEIGHT = 720;
const SNAPSHOT_VERSION = "d3-force-layout-v2";

function hash(value) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function seededRandom(seed) {
  let state = seed || 1;
  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function anchorsFor(nodes) {
  const types = [...new Set(nodes.map((node) => node.type))].sort();
  return new Map(types.map((type, index) => {
    const angle = types.length === 1 ? 0 : index / types.length * Math.PI * 2 - Math.PI / 2;
    const radius = types.length === 1 ? 0 : Math.min(275, 118 + types.length * 14);
    return [type, {
      x: WIDTH / 2 + Math.cos(angle) * radius,
      y: HEIGHT / 2 + Math.sin(angle) * radius * 0.72,
    }];
  }));
}

function readSnapshot(key, ids) {
  try {
    const value = JSON.parse(window.localStorage.getItem(key) || "null");
    if (value?.version !== SNAPSHOT_VERSION || !value.positions) return null;
    if (!ids.every((id) => value.positions[id])) return null;
    return value.positions;
  } catch (_) {
    return null;
  }
}

function writeSnapshot(key, positions) {
  try {
    window.localStorage.setItem(key, JSON.stringify({
      version: SNAPSHOT_VERSION,
      positions: Object.fromEntries(positions),
    }));
  } catch (_) {
    // Layout remains deterministic when browser storage is unavailable.
  }
}

function layout(rawNodes, rawEdges, signature) {
  const ids = rawNodes.map((node) => String(node.id));
  const key = `hermes.graph-layout.v1.${hash(signature).toString(16)}`;
  const snapshot = readSnapshot(key, ids);
  if (snapshot) return new Map(ids.map((id) => [id, snapshot[id]]));

  const nodes = rawNodes.map((node) => ({
    id: String(node.id),
    type: String(node.object_type || node.kind || "evidence"),
  }));
  const anchors = anchorsFor(nodes);
  const offsets = new Map();
  nodes.forEach((node) => {
    const index = offsets.get(node.type) || 0;
    offsets.set(node.type, index + 1);
    const anchor = anchors.get(node.type);
    const angle = index * 2.399963229728653;
    const radius = Math.min(104, 14 + Math.sqrt(index) * 22);
    node.x = anchor.x + Math.cos(angle) * radius;
    node.y = anchor.y + Math.sin(angle) * radius * 0.72;
  });
  const nodeIds = new Set(ids);
  const links = rawEdges
    .filter((edge) => nodeIds.has(String(edge.source)) && nodeIds.has(String(edge.target)))
    .map((edge) => ({ source: String(edge.source), target: String(edge.target) }));
  const simulation = forceSimulation(nodes)
    .randomSource(seededRandom(hash(signature)))
    .force("link", forceLink(links).id((node) => node.id).distance(132).strength(0.16))
    .force("charge", forceManyBody().strength(-180).distanceMax(340))
    .force("collision", forceCollide().radius(30).strength(0.92).iterations(2))
    .force("category-x", forceX((node) => anchors.get(node.type).x).strength(0.12))
    .force("category-y", forceY((node) => anchors.get(node.type).y).strength(0.12))
    .stop();
  for (let index = 0; index < 180; index += 1) simulation.tick();
  simulation.stop();
  const positions = new Map(nodes.map((node) => [node.id, {
    x: Math.max(28, Math.min(WIDTH - 28, node.x)),
    y: Math.max(28, Math.min(HEIGHT - 28, node.y)),
  }]));
  writeSnapshot(key, positions);
  return positions;
}

window.InvarianceGraphLayout = Object.freeze({ layout, version: SNAPSHOT_VERSION });
