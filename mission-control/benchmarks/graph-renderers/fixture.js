function graphFixture(nodeCount) {
  const types = ["source", "claim", "result", "method", "dataset", "review", "decision"];
  const predicates = ["supports", "contradicts", "derived_from", "uses_method", "uses_dataset", "cites"];
  const nodes = Array.from({ length: nodeCount }, (_, index) => ({
    id: `node-${index}`,
    label: `Evidence record ${index}`,
    object_type: types[index % types.length],
  }));
  const edges = [];
  for (let index = 1; index < nodeCount; index += 1) {
    edges.push({ id: `edge-${index}-tree`, source: `node-${Math.floor((index - 1) / 2)}`, target: `node-${index}`, predicate: predicates[index % predicates.length] });
    if (index > 5 && index % 3 === 0) edges.push({ id: `edge-${index}-cross`, source: `node-${index - 5}`, target: `node-${index}`, predicate: predicates[(index + 2) % predicates.length] });
  }
  return { nodes, edges };
}

function deterministicPositions(nodes) {
  const positions = new Map();
  nodes.forEach((node, index) => {
    const angle = index * 2.399963;
    const radius = Math.min(220, 36 + Math.sqrt(index) * 30);
    positions.set(node.id, { x: 450 + Math.cos(angle) * radius, y: 260 + Math.sin(angle) * radius * .78 });
  });
  return positions;
}
