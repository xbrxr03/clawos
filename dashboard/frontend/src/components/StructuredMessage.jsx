/**
 * StructuredMessage — renders Nexus chat responses with proper formatting.
 *
 * Detects and renders:
 *   - Markdown headers (## / ###) as styled section blocks
 *   - Bullet/numbered lists as proper list blocks
 *   - Code blocks (``` fenced) as monospace blocks
 *   - Inline code (`backtick`) as styled spans
 *   - Bold (**text**) and italic (*text*)
 *   - Follow-up suggestions (lines starting with "?") as clickable chips
 *   - Plain text as paragraphs
 *
 * Replaces plain-text {message.text} rendering in NexusCommand and Brain.
 * Zero external dependencies — pure React.
 */
import React from 'react'

/**
 * Parse inline formatting: bold, italic, inline code
 */
function renderInline(text) {
  const parts = []
  let remaining = text
  let key = 0

  while (remaining.length > 0) {
    // Inline code
    const codeMatch = remaining.match(/`([^`]+)`/)
    // Bold
    const boldMatch = remaining.match(/\*\*([^*]+)\*\*/)
    // Italic (single *)
    const italicMatch = remaining.match(/(?<!\*)\*([^*]+)\*(?!\*)/)

    // Find the earliest match
    const matches = [
      codeMatch && { type: 'code', match: codeMatch },
      boldMatch && { type: 'bold', match: boldMatch },
      italicMatch && { type: 'italic', match: italicMatch },
    ].filter(Boolean).sort((a, b) => a.match.index - b.match.index)

    if (matches.length === 0) {
      parts.push(remaining)
      break
    }

    const first = matches[0]
    const idx = first.match.index

    if (idx > 0) {
      parts.push(remaining.slice(0, idx))
    }

    if (first.type === 'code') {
      parts.push(
        <code key={key++} style={{
          background: 'var(--fill-2, rgba(255,255,255,0.08))',
          padding: '1px 5px',
          borderRadius: 4,
          fontSize: '0.9em',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          {first.match[1]}
        </code>
      )
    } else if (first.type === 'bold') {
      parts.push(<strong key={key++}>{first.match[1]}</strong>)
    } else if (first.type === 'italic') {
      parts.push(<em key={key++}>{first.match[1]}</em>)
    }

    remaining = remaining.slice(idx + first.match[0].length)
  }

  return parts
}

/**
 * Parse a message string into structured blocks.
 */
function parseBlocks(text) {
  if (!text || typeof text !== 'string') return [{ type: 'text', content: String(text || '') }]

  const lines = text.split('\n')
  const blocks = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block (fenced)
    if (line.trim().startsWith('```')) {
      const lang = line.trim().slice(3).trim()
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      blocks.push({ type: 'code', content: codeLines.join('\n'), lang })
      i++ // skip closing ```
      continue
    }

    // Header
    if (/^#{1,3}\s+/.test(line)) {
      const level = line.match(/^(#{1,3})/)[1].length
      const content = line.replace(/^#{1,3}\s+/, '')
      blocks.push({ type: 'header', content, level })
      i++
      continue
    }

    // Follow-up suggestion (? prefix)
    if (/^\?\s+/.test(line.trim())) {
      const suggestions = []
      while (i < lines.length && /^\?\s+/.test(lines[i].trim())) {
        suggestions.push(lines[i].trim().replace(/^\?\s+/, ''))
        i++
      }
      blocks.push({ type: 'followup', items: suggestions })
      continue
    }

    // List item (bullet or numbered)
    if (/^\s*[-*+]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      const items = []
      while (i < lines.length && (/^\s*[-*+]\s+/.test(lines[i]) || /^\s*\d+[.)]\s+/.test(lines[i]))) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, '').replace(/^\s*\d+[.)]\s+/, ''))
        i++
      }
      blocks.push({ type: 'list', items })
      continue
    }

    // Empty line
    if (line.trim() === '') {
      i++
      continue
    }

    // Plain text — collect consecutive non-empty, non-special lines
    const textLines = []
    while (i < lines.length && lines[i].trim() !== '' &&
           !lines[i].trim().startsWith('```') &&
           !/^#{1,3}\s+/.test(lines[i]) &&
           !/^\s*[-*+]\s+/.test(lines[i]) &&
           !/^\s*\d+[.)]\s+/.test(lines[i]) &&
           !/^\?\s+/.test(lines[i].trim())) {
      textLines.push(lines[i])
      i++
    }
    if (textLines.length > 0) {
      blocks.push({ type: 'text', content: textLines.join('\n') })
    }
  }

  return blocks
}


/**
 * Render a structured message from Nexus.
 *
 * @param {Object} props
 * @param {string} props.text - The raw message text
 * @param {function} [props.onFollowUp] - Callback when a follow-up suggestion is clicked
 */
export default function StructuredMessage({ text, onFollowUp }) {
  const blocks = parseBlocks(text)

  if (blocks.length === 1 && blocks[0].type === 'text' && !blocks[0].content.includes('`') && !blocks[0].content.includes('**')) {
    // Simple plain text — render as-is for efficiency
    return <span>{blocks[0].content}</span>
  }

  return (
    <div className="structured-message" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'header':
            return (
              <div key={idx} style={{
                fontSize: block.level === 1 ? 15 : block.level === 2 ? 13 : 12,
                fontWeight: 600,
                color: 'var(--text-1, #fff)',
                marginTop: idx > 0 ? 4 : 0,
              }}>
                {renderInline(block.content)}
              </div>
            )

          case 'list':
            return (
              <div key={idx} style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                paddingLeft: 12,
                borderLeft: '2px solid var(--blue, #007AFF)',
              }}>
                {block.items.map((item, j) => (
                  <div key={j} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                    <span style={{ color: 'var(--blue, #007AFF)', fontWeight: 700, flexShrink: 0 }}>-</span>
                    <span>{renderInline(item)}</span>
                  </div>
                ))}
              </div>
            )

          case 'code':
            return (
              <pre key={idx} style={{
                background: 'var(--fill-2, rgba(0,0,0,0.25))',
                border: '0.5px solid var(--separator, rgba(255,255,255,0.1))',
                borderRadius: 8,
                padding: '8px 10px',
                fontSize: 11,
                fontFamily: 'var(--font-mono, monospace)',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
              }}>
                {block.lang && (
                  <div style={{
                    fontSize: 9,
                    color: 'var(--text-3, rgba(255,255,255,0.4))',
                    marginBottom: 4,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}>
                    {block.lang}
                  </div>
                )}
                <code>{block.content}</code>
              </pre>
            )

          case 'followup':
            return (
              <div key={idx} style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
                marginTop: 4,
              }}>
                {block.items.map((item, j) => (
                  <button
                    key={j}
                    onClick={() => onFollowUp && onFollowUp(item)}
                    style={{
                      background: 'var(--fill-2, rgba(0, 122, 255, 0.1))',
                      border: '0.5px solid var(--blue-dim, rgba(0, 122, 255, 0.24))',
                      borderRadius: 999,
                      padding: '4px 12px',
                      fontSize: 11,
                      color: 'var(--blue, #007AFF)',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseOver={(e) => e.target.style.background = 'rgba(0, 122, 255, 0.18)'}
                    onMouseOut={(e) => e.target.style.background = 'var(--fill-2, rgba(0, 122, 255, 0.1))'}
                  >
                    {item}
                  </button>
                ))}
              </div>
            )

          case 'text':
          default:
            return (
              <div key={idx} style={{ lineHeight: 1.5 }}>
                {renderInline(block.content)}
              </div>
            )
        }
      })}
    </div>
  )
}
