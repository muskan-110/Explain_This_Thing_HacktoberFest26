import { useEffect, useRef, useState } from 'react'
import type { Appliance, ExplainResponse, Health, Language } from '../types'
import { explain, getAppliances, getHealth, panelUrl } from '../api'
import { strings } from '../i18n'
import TapImage, { type TapPoint } from '../components/TapImage'
import AnswerCard from '../components/AnswerCard'

interface Props {
  language: Language
}

const REQUEST_TIMEOUT_MS = 240_000

export default function Home({ language }: Props) {
  const t = strings(language)

  const [customFile, setCustomFile] = useState<File | null>(null)
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [usingSaved, setUsingSaved] = useState(false)
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [savedId, setSavedId] = useState('')
  const [useKb, setUseKb] = useState(true)
  const [tap, setTap] = useState<TapPoint | null>(null)
  const [imageFailed, setImageFailed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [response, setResponse] = useState<ExplainResponse | null>(null)
  const [answerLang, setAnswerLang] = useState<Language>(language)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    getAppliances()
      .then((list) => {
        setAppliances(list)
        // There is no "None" choice any more: start on the first saved appliance.
        setSavedId((current) => current || list[0]?.id || '')
      })
      .catch(() => setAppliances([]))
    getHealth().then(setHealth).catch(() => setHealth(null))
    return () => abortRef.current?.abort()
  }, [])

  useEffect(
    () => () => {
      if (customUrl) URL.revokeObjectURL(customUrl)
    },
    [customUrl],
  )

  useEffect(() => {
    if (!loading) return
    setElapsed(0)
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [loading])

  // The photo shown: the user's own, or (only if asked for) the saved appliance's stored photo.
  const imageSrc = customUrl ?? (usingSaved && savedId ? panelUrl(savedId) : null)
  const hasPhoto = Boolean(imageSrc) && !imageFailed

  function resetResult() {
    setTap(null)
    setResponse(null)
    setError(null)
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCustomFile(file)
    setCustomUrl(URL.createObjectURL(file))
    setImageFailed(false)
    resetResult()
    e.target.value = ''
  }

  function handleSavedChange(id: string) {
    setSavedId(id)
    setImageFailed(false)
    resetResult()
  }

  function useSavedPhoto() {
    setUsingSaved(true)
    setImageFailed(false)
    resetResult()
  }

  // Back to the front page: forget the photo and any answer, and cancel a running request.
  function goBack() {
    const controller = abortRef.current
    abortRef.current = null
    controller?.abort()
    setCustomFile(null)
    setCustomUrl(null)
    setUsingSaved(false)
    setImageFailed(false)
    setLoading(false)
    resetResult()
  }

  async function ask() {
    if (!tap || loading || !imageSrc) return
    const controller = new AbortController()
    abortRef.current = controller
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const res = await explain(
        {
          applianceId: savedId || null,
          applianceType: null,
          x: tap.x,
          y: tap.y,
          language,
          useKb: savedId ? useKb : false,
          image: customFile,
        },
        controller.signal,
      )
      if (abortRef.current !== controller) return // the user went back meanwhile
      setResponse(res)
      setAnswerLang(language)
    } catch (err) {
      if (abortRef.current !== controller) return // cancelled by "Back", not a real error
      setError(controller.signal.aborted ? t.timedOut : err instanceof Error ? err.message : String(err))
    } finally {
      window.clearTimeout(timer)
      if (abortRef.current === controller) setLoading(false)
    }
  }

  const stepText = elapsed < 4 ? t.loading1 : elapsed < 12 ? t.loading2 : t.loading3

  return (
    <main className="page">
      {health && health.ollama === false && <div className="banner banner-warn">{t.ollamaDown}</div>}

      {imageFailed && usingSaved && !customUrl && <div className="banner banner-warn">{t.noPhoto}</div>}

      {!hasPhoto ? (
        <label className="upload-card">
          <span className="upload-icon">📷</span>
          <span className="upload-title">{t.uploadTitle}</span>
          <span className="muted">{t.uploadSub}</span>
          <input type="file" accept="image/*" capture="environment" onChange={handleFile} hidden />
        </label>
      ) : (
        <>
          <button type="button" className="back" onClick={goBack}>
            ← {t.back}
          </button>
          <p className="hint">👆 {t.tapHint}</p>
          <TapImage
            src={imageSrc as string}
            marker={tap}
            onTap={(p) => {
              setTap(p)
              setResponse(null)
              setError(null)
            }}
            onImageError={() => setImageFailed(true)}
          />
          <div className="controls">
            <label className="btn btn-secondary file-btn">
              📷 {t.changePhoto}
              <input type="file" accept="image/*" capture="environment" onChange={handleFile} hidden />
            </label>
          </div>
        </>
      )}

      {appliances.length > 0 && (
        <div className="field">
          <label className="field-label" htmlFor="saved">
            {t.savedNotes}
          </label>
          <select id="saved" className="select" value={savedId} onChange={(e) => handleSavedChange(e.target.value)}>
            {appliances.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.has_knowledge ? ` (${t.notesCount(a.chunk_count ?? 0)})` : ''}
              </option>
            ))}
          </select>
          <label className="switch">
            <input type="checkbox" checked={useKb} onChange={(e) => setUseKb(e.target.checked)} />
            <span>{t.useNotes}</span>
          </label>
          {!hasPhoto && (
            <button type="button" className="btn btn-secondary" onClick={useSavedPhoto}>
              {t.useSavedPhoto}
            </button>
          )}
        </div>
      )}

      {hasPhoto && (
        <button type="button" className="btn btn-primary" disabled={!tap || loading} onClick={ask}>
          {loading ? stepText : tap ? t.ask : t.tapFirst}
        </button>
      )}

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