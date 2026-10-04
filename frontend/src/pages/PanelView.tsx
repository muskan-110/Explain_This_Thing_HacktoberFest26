import { useEffect, useRef, useState } from 'react'
import type { Appliance, ExplainResponse, Language } from '../types'
import { explain, panelUrl } from '../api'
import { strings } from '../i18n'
import TapImage, { type TapPoint } from '../components/TapImage'
import AnswerCard from '../components/AnswerCard'

interface Props {
  appliance: Appliance
  language: Language
  onBack: () => void
}

const REQUEST_TIMEOUT_MS = 180_000

export default function PanelView({ appliance, language, onBack }: Props) {
  const t = strings(language)

  const [tap, setTap] = useState<TapPoint | null>(null)
  const [customFile, setCustomFile] = useState<File | null>(null)
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [imageMissing, setImageMissing] = useState(false)
  const [useKb, setUseKb] = useState(true)
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [response, setResponse] = useState<ExplainResponse | null>(null)
  const [answerLang, setAnswerLang] = useState<Language>(language)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Cancel any in-flight request when leaving the page.
  useEffect(() => () => abortRef.current?.abort(), [])

  // Free the temporary URL of an uploaded photo.
  useEffect(
    () => () => {
      if (customUrl) URL.revokeObjectURL(customUrl)
    },
    [customUrl],
  )

  // Count seconds while waiting, to rotate the progress text.
  useEffect(() => {
    if (!loading) return
    setElapsed(0)
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [loading])

  const imageSrc = customUrl ?? panelUrl(appliance.id)

  function handleTap(point: TapPoint) {
    setTap(point)
    setResponse(null)
    setError(null)
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCustomFile(file)
    setCustomUrl(URL.createObjectURL(file))
    setImageMissing(false)
    setTap(null)
    setResponse(null)
    setError(null)
    e.target.value = ''
  }

  function useSavedPhoto() {
    setCustomFile(null)
    setCustomUrl(null)
    setImageMissing(false)
    setTap(null)
    setResponse(null)
    setError(null)
  }

  async function ask() {
    if (!tap || loading) return
    const controller = new AbortController()
    abortRef.current = controller
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const res = await explain(
        { applianceId: appliance.id, x: tap.x, y: tap.y, language, useKb, image: customFile },
        controller.signal,
      )
      setResponse(res)
      setAnswerLang(language)
    } catch (err) {
      if (controller.signal.aborted) {
        setError(t.timedOut)
      } else {
        setError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      window.clearTimeout(timer)
      setLoading(false)
    }
  }

  const stepText = elapsed < 4 ? t.loading1 : elapsed < 12 ? t.loading2 : t.loading3

  return (
    <main className="page">
      <button type="button" className="back" onClick={onBack}>
        ← {t.back}
      </button>

      <h2 className="page-title">{appliance.name}</h2>

      {imageMissing ? (
        <div className="banner banner-warn">{t.noPhoto}</div>
      ) : (
        <>
          <p className="hint">👆 {t.tapHint}</p>
          <TapImage
            src={imageSrc}
            marker={tap}
            onTap={handleTap}
            onImageError={() => setImageMissing(true)}
            onImageLoad={() => setImageMissing(false)}
          />
        </>
      )}

      <div className="controls">
        <label className="btn btn-secondary file-btn">
          📷 {t.uploadPhoto}
          <input type="file" accept="image/*" capture="environment" onChange={handleFile} hidden />
        </label>
        {customFile && (
          <button type="button" className="btn btn-secondary" onClick={useSavedPhoto}>
            {t.useSavedPhoto}
          </button>
        )}
        <label className="switch">
          <input type="checkbox" checked={useKb} onChange={(e) => setUseKb(e.target.checked)} />
          <span>{t.useNotes}</span>
        </label>
      </div>

      <button type="button" className="btn btn-primary" disabled={!tap || loading} onClick={ask}>
        {loading ? stepText : tap ? t.ask : t.tapFirst}
      </button>

      {loading && (
        <div className="loading" aria-live="polite">
          <div className="spinner" />
          {elapsed > 25 && <p className="muted small">{t.slowNote}</p>}
        </div>
      )}

      {error && (
        <div className="banner banner-error">
          <strong>{t.errorTitle}</strong>
          <div>{error}</div>
        </div>
      )}

      {response && (
        <>
          {answerLang !== language && <div className="banner banner-warn">{t.otherLang}</div>}
          <AnswerCard response={response} answerLang={answerLang} />
        </>
      )}
    </main>
  )
}
