
import { parser } from "@lezer/markdown"

const input = `\`\`\`typescript
const x = 42;
console.log(x);
\`\`\`

Some text after.

\`\`\`python
def foo():
    pass
\`\`\`
`

const tree = parser.parse(input)

function printTree(node, depth = 0) {
  const text = input.slice(node.from, node.to)
  const preview = text.length > 40 ? text.substring(0, 40) + '...' : text.replace(/\n/g, '\\n')
  console.log('  '.repeat(depth) + `${node.type.name} [${node.from}-${node.to}] "${preview}"`)
  let child = node.firstChild
  while (child) {
    printTree(child, depth + 1)
    child = child.nextSibling
  }
}

printTree(tree.topNode)
