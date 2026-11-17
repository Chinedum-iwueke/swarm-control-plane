import json
from pathlib import Path
import subprocess


def test_episode_renderer_preserves_unknown_usage_attempt_scope_and_escaping():
    app = (Path(__file__).parents[1]/"src/hermes_mission_control/static/app.js").read_text()
    source = app.split("function renderEpisodeEvidence(", 1)[1].split("\nfunction openOperation", 1)[0]
    task = dict(task_type="alpha_method_design", status="running", attempt_count=2,
                assigned_agent_id="<operator>", input_contract={"policy": {"max_model_calls": 3}},
                result={})
    events = [
        dict(event_type="task_heartbeat", attempt_number=1, payload={"progress": {"stage": "old"}},
             created_at="old"),
        dict(event_type="task_heartbeat", attempt_number=2, payload={"progress": {
            "stage": "diagnose", "model_calls": 0, "blocker": "<script>", "usage_complete": False}},
             created_at="current"),
    ]
    code = """
const assert = require('node:assert/strict');
const escapeHtml = v => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const humanize = v => v;
const formatDate = v => v;
""" + "function renderEpisodeEvidence(" + source + """
const html = renderEpisodeEvidence(TASK, EVENTS);
assert(html.includes('diagnose'));
assert(!html.includes('>old<'));
assert(html.includes('Unknown or incomplete'));
assert(html.includes('0 / 3'));
assert(html.includes('&lt;script&gt;'));
assert(!html.includes('<script>'));
assert(html.includes('<details>'));
const finished = {...TASK, status:'succeeded', result:{summary:{method_episode:{state:{
  status:'deferred', reason:'repair_budget_exhausted', model_calls:3
}}}}};
const terminal = renderEpisodeEvidence(finished, EVENTS);
assert(terminal.includes('repair_budget_exhausted'));
assert(terminal.includes('3 / 3'));
assert(terminal.includes('Retained terminal result'));
assert(!terminal.includes('>diagnose<'));
assert(terminal.includes('Recovery condition'));
""".replace("TASK", json.dumps(task)).replace("EVENTS", json.dumps(events))
    subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True)
