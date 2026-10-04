import type { Language } from '../types'

interface Props {
  language: Language
  onChange: (lang: Language) => void
}

export default function LanguageToggle({ language, onChange }: Props) {
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        type="button"
        className={language === 'en' ? 'active' : ''}
        onClick={() => onChange('en')}
      >
        English
      </button>
      <button
        type="button"
        className={language === 'hi' ? 'active' : ''}
        onClick={() => onChange('hi')}
      >
        हिन्दी
      </button>
    </div>
  )
}
