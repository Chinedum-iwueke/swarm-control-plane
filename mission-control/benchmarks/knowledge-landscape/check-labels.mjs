import assert from "node:assert/strict";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true });
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    await page.goto(`${process.env.GRAPH_TEST_URL || "http://127.0.0.1:8797/static/index.html"}?demo=1&view=knowledge`);
    await page.waitForFunction(() => typeof renderGraph === "function" && state.dashboard);
    await page.evaluate(() => {
      setResearchMode("explore");
      state.graphView = "visual";
      const nodes = Array.from({ length: 50 }, (_, i) => ({ id: `label-test-${i}`, object_type: "hypothesis", label: `Research question ${i}: cross-asset volatility and market evidence` }));
      renderGraph({ nodes, edges: nodes.slice(1).map((node, i) => ({ source: nodes[i].id, target: node.id, predicate: "derived_from" })) });
    });
    const counts = await page.evaluate(() => {
      const nodes = [...document.querySelectorAll(".graph-node-svg")];
      const visible = nodes.filter((node) => !node.querySelector(".graph-node-caption").classList.contains("label-occluded"));
      for (const node of nodes) {
        if (Math.abs(Number(node.querySelector(".graph-node-label").getAttribute("x"))) !== 20) throw new Error("Detached label");
      }
      const bounds = visible.map((node) => node.querySelector("text").getBoundingClientRect());
      for (let i = 0; i < bounds.length; i++) for (let j = i + 1; j < bounds.length; j++) {
        const a = bounds[i], b = bounds[j];
        if (a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top) throw new Error("Default labels overlap");
      }
      return { total: nodes.length, visible: visible.length };
    });
    assert.equal(counts.total, 50);
    assert.ok(counts.visible > 0 && counts.visible < 50, JSON.stringify(counts));
    const hiddenId = await page.locator(".graph-node-svg:has(.label-occluded)").first().getAttribute("data-graph-node");
    const hidden = page.locator(`.graph-node-svg[data-graph-node="${hiddenId}"]`);
    await hidden.focus();
    assert.equal(await hidden.locator(".graph-node-caption").evaluate((el) => getComputedStyle(el).visibility), "visible");
    await page.evaluate(() => {
      const node = document.querySelector(".graph-node-svg.selected");
      state.graphLayout.set(node.dataset.graphNode, { x: 450, y: 320 });
      updateGraphSvgPositions();
      if (node.getAttribute("transform") !== "translate(450 320)") throw new Error("Drag did not move node and caption together");
    });
    await page.screenshot({ path: `/tmp/graph-labels-${width}.png`, fullPage: true });
    console.log(JSON.stringify({ width, ...counts, keyboardReveal: true, attachedAfterMove: true }));
    await page.close();
  }
} finally {
  await browser.close();
}
