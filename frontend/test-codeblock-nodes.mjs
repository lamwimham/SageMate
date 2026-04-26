
import { MarkdownParser } from "@lezer/markdown";
import { parser as mdParser } from "@lezer/markdown";

// Test different code block states
const testCases = [
  { name: "Complete fenced code", content: "```python\nprint('hello')\n```" },
  { name: "Opening only - just ticks", content: "```" },
  { name: "Opening only - with lang", content: "```python" },
  { name: "Opening + content, no close", content: "```python\nprint('hello')" },
  { name: "Opening + content + newline, no close", content: "```python\nprint('hello')\n" },
  { name: "With text before and after opening", content: "Hello\n```python\nworld\n```" },
  { name: "Just closing ticks", content: "```" },
];

for (const tc of testCases) {
  const tree = mdParser.parse(tc.content);
  console.log(`\n=== ${tc.name} ===`);
  console.log(`Content: ${JSON.stringify(tc.content)}`);
  console.log("Tree:", tree.topNode.toString());
  tree.iterate({
    enter(node) {
      console.log(`  ${node.name} [${node.from}-${node.to}] "${tc.content.slice(node.from, node.to)}"`);
    }
  });
}
