import { useState } from 'react'
import type { ExplainResponse, Language } from '../types'
import { strings } from '../i18n'
import { sendFeedback } from '../api'
import SourceBadge from './SourceBadge'

interface Props {
  response: ExplainResponse
  answerLang: Language
}

function speak(text: string, lang: Language) {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = lang === 'hi' ? 'hi-IN' : 'en-IN'
  const voices = window.speechSynthesis.getVoices()
  const voice =
    voices.find((v) => v.lang.toLowerCase() === utterance.lang.toLowerCase()) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(lang))
  if (voice) utterance.voice = voice
  window.speechSynthesis.speak(utterance)
}

export default function AnswerCard({ response, answerLang }: Props) {
  const t = strings(answerLang)
  const { card } = response
  const [feedback, setFeedback] = useState<'none' | 'sent' | 'failed'>('none')

  const sure =
    card.confidence === 'high'
      ? { label: t.sureHigh, cls: 'chip-green' }
      : card.confidence === 'medium'
        ? { label: t.sureMedium, cls: 'chip-amber' }
        : { label: t.sureLow, cls: 'chip-red' }

  async function giveFeedback(helpful: boolean) {
    try {
      await sendFeedback(response.request_id, helpful)
      setFeedback('sent')
    } catch {
      setFeedback('failed')
    }
  }

  const spoken = `${card.button_name}. ${card.what_it_does} ${card.try_this}`

  return (
    <section className="answer">
      {card.safety_flag && <div className="safety">⚠️ {t.safety}</div>}

      <div className="answer-top">
        <h2 className="answer-title">{card.button_name}</h2>
        <span className={`chip ${sure.cls}`}>{sure.label}</span>
      </div>

      <SourceBadge card={card} t={t} />

      {card.hindi_failed && <p className="note">{t.hindiFailed}</p>}

      <h3 className="answer-label">{t.whatItDoes}</h3>
      <p className="answer-text">{card.what_it_does}</p>

      <h3 className="answer-label">{t.tryThis}</h3>
      <p className="answer-text">{card.try_this}</p>

      <button type="button" className="btn btn-secondary" onClick={() => speak(spoken, answerLang)}>
        🔊 {t.readAloud}
      </button>

      <div className="feedback">
        {feedback === 'sent' ? (
          <span>{t.thanks}</span>
        ) : (
          <>
            <span>{t.helpful}</span>
            <button type="button" className="btn-small" onClick={() => giveFeedback(true)}>
              👍 {t.yes}
            </button>
            <button type="button" className="btn-small" onClick={() => giveFeedback(false)}>
              👎 {t.no}
            </button>
            {feedback === 'failed' && <span className="note">Could not save feedback.</span>}
          </>
        )}
      </div>

      <details className="details">
        <summary>{t.details}</summary>
        <div className="details-body">
          {response.cropped_image_base64 && (
            <p>
              What the model looked at:
              <br />
              <img
                className="crop-preview"
                alt="Cropped area around the tapped button"
                src={`data:image/jpeg;base64,${response.cropped_image_base64}`}
              />
            </p>
          )}
          {response.mode && <p>mode: {response.mode}</p>}
          {response.read_result && (
            <p>
              read: “{response.read_result.label_text ?? ''}” — {response.read_result.icon_description ?? ''}
            </p>
          )}
          {response.timings && (
            <p>
              timings:{' '}
              {Object.entries(response.timings)
                .map(([k, v]) => `${k.replace('_ms', '')} ${(v / 1000).toFixed(1)}s`)
                .join(', ')}
            </p>
          )}
          {response.retrieved_chunks && response.retrieved_chunks.length > 0 && (
            <ul>
              {response.retrieved_chunks.map((c, i) => (
                <li key={i}>
                  {c.filename} / {c.heading} — {c.score.toFixed(2)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </details>
    </section>
  )
}
