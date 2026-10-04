import type { Card } from '../types'
import type { Strings } from '../i18n'

interface Props {
  card: Card
  t: Strings
}

export default function SourceBadge({ card, t }: Props) {
  if (card.source === 'knowledge_base' && card.source_ref) {
    return (
      <div className="badge badge-green">
        <strong>{t.fromNotes}</strong> {card.source_ref}
      </div>
    )
  }
  if (card.source === 'knowledge_base') {
    return <div className="badge badge-amber">{t.sourceUnclear}</div>
  }
  return <div className="badge badge-amber">{t.notFromManual}</div>
}
