import { useEffect, useState } from 'react'
import type { Appliance, Health, Language } from '../types'
import { getAppliances, getHealth, panelUrl } from '../api'
import { strings } from '../i18n'

interface Props {
  language: Language
  onSelect: (appliance: Appliance) => void
}

export default function ApplianceList({ language, onSelect }: Props) {
  const t = strings(language)
  const [appliances, setAppliances] = useState<Appliance[] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getAppliances()
      .then((list) => {
        if (!cancelled) setAppliances(list)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
    getHealth()
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch(() => {
        // health is optional; the list error above already covers an unreachable server
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="page">
      <h2 className="page-title">{t.chooseAppliance}</h2>

      {health && health.ollama === false && <div className="banner banner-warn">{t.ollamaDown}</div>}
      {error && (
        <div className="banner banner-error">
          <strong>{t.errorTitle}</strong>
          <div>{error}</div>
        </div>
      )}
      {!error && appliances === null && <p className="muted">{t.loadingAppliances}</p>}
      {appliances && appliances.length === 0 && <p className="muted">{t.noAppliances}</p>}

      <div className="grid">
        {appliances?.map((a) => {
          const subtitle = [a.brand, a.model].filter(Boolean).join(' · ')
          return (
            <button key={a.id} type="button" className="appliance-card" onClick={() => onSelect(a)}>
              <div className="appliance-img-wrap">
                <img
                  src={panelUrl(a.id)}
                  alt=""
                  className="appliance-img"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
              </div>
              <div className="appliance-info">
                <div className="appliance-name">
                  {a.name}
                  {a.id.startsWith('_') && <span className="tag">{t.sample}</span>}
                </div>
                {subtitle && <div className="muted small">{subtitle}</div>}
                <span className={`badge ${a.has_knowledge ? 'badge-green' : 'badge-amber'}`}>
                  {a.has_knowledge ? t.notes(a.chunk_count ?? 0) : t.noManual}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </main>
  )
}
