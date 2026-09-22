"""The chat renderer must handle the Markdown Stuart actually writes."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from ui.app import STATIC_DIR

HARNESS = """
function makeNode(tag) {
  return {
    tag,
    className: "",
    textContent: "",
    dataset: {},
    children: [],
    append(...kids) {
      for (const kid of kids) {
        if (kid.tag === "#fragment") this.children.push(...kid.children);
        else this.children.push(kid);
      }
    },
  };
}

const document = {
  createElement: makeNode,
  createDocumentFragment: () => makeNode("#fragment"),
  createTextNode: (value) => {
    const node = makeNode("#text");
    node.textContent = value;
    return node;
  },
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

__RENDERER__

function textOf(node) {
  return node.textContent || node.children.map(textOf).join("");
}

const rows = formatDraft(SAMPLE).children.map((node) => ({
  tag: node.tag,
  className: node.className,
  marker: node.dataset.marker || "",
  text: textOf(node),
}));
console.log(JSON.stringify(rows));
"""

SAMPLE = "\n".join(
    [
        "### **Q3-FY26 Opportunities**",
        "* **Meridian Bank** — $580,000, owned by Elena Rodriguez",
        "  * Close date 2026-09-29",
        "---",
        "1. Assign a Lead SE to Zenith Health.",
        "Stage code is `SS40` today.",
        "```",
        "Hi Elena,",
        "```",
    ]
)


def _render() -> list[dict[str, str]]:
    source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    renderer = source[
        source.index("const INLINE_RE") : source.index("function addReplyCopy")
    ]
    script = HARNESS.replace("__RENDERER__", renderer).replace(
        "SAMPLE", json.dumps(SAMPLE)
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_renderer_handles_every_markdown_shape_stuart_writes() -> None:
    rows = _render()
    assert [row["className"] for row in rows] == [
        "draft-subhead",
        "draft-bullet",
        "draft-bullet draft-indent",
        "draft-rule",
        "draft-step",
        "draft-line",
        "draft-code",
    ]
    assert rows[0]["text"] == "Q3-FY26 Opportunities"
    assert rows[1]["text"].startswith("Meridian Bank — $580,000")
    assert rows[3]["tag"] == "hr"
    assert rows[4]["marker"] == "1."
    assert rows[5]["text"] == "Stage code is SS40 today."
    assert rows[6]["text"] == "Hi Elena,"
