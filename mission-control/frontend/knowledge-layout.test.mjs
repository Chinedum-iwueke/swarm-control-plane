import assert from "node:assert/strict";

const storage = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  },
};
await import("./knowledge-layout.js");

const nodes = Array.from({ length: 30 }, (_, index) => ({
  id: `node-${index}`,
  object_type: ["hypothesis", "dataset", "method", "run", "result"][index % 5],
}));
const edges = nodes.slice(1).map((node, index) => ({
  source: nodes[index].id,
  target: node.id,
  predicate: "derived_from",
}));
const signature = "deterministic-layout-fixture-v1";
const first = window.InvarianceGraphLayout.layout(nodes, edges, signature);
storage.clear();
const second = window.InvarianceGraphLayout.layout(nodes, edges, signature);

assert.deepEqual([...first], [...second]);
assert.equal(first.size, nodes.length);
for (const position of first.values()) {
  assert.ok(position.x >= 28 && position.x <= 872);
  assert.ok(position.y >= 28 && position.y <= 492);
}
let nearest = Number.POSITIVE_INFINITY;
const positions = [...first.values()];
for (let left = 0; left < positions.length; left += 1) {
  for (let right = left + 1; right < positions.length; right += 1) {
    nearest = Math.min(
      nearest,
      Math.hypot(
        positions[left].x - positions[right].x,
        positions[left].y - positions[right].y,
      ),
    );
  }
}
assert.ok(nearest >= 18, `collision distance ${nearest} was below 18px`);
