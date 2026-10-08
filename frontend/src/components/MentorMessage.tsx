import { Fragment } from 'react'

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) =>
    part.startsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> :
    part.startsWith('`') ? <code key={index}>{part.slice(1, -1)}</code> : <Fragment key={index}>{part}</Fragment>)
}

export function MentorMessage({ text }: { text: string }) {
  return <div className="mentor-message">{text.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split('\n')
    if (lines.every(line => /^\s*[-*] /.test(line))) return <ul key={index}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*[-*] /, ''))}</li>)}</ul>
    if (lines.every(line => /^\s*\d+[.)] /.test(line))) return <ol key={index}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*\d+[.)] /, ''))}</li>)}</ol>
    if (/^#{1,6} /.test(block)) return <h3 key={index}>{inline(block.replace(/^#{1,6} /, ''))}</h3>
    return <p key={index}>{lines.map((line, item) => <Fragment key={item}>{item > 0 && <br />}{inline(line)}</Fragment>)}</p>
  })}</div>
}
