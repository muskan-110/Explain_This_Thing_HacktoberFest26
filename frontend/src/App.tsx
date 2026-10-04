import { useState } from 'react'
import type { Language } from './types'
import { strings } from './i18n'
import LanguageToggle from './components/LanguageToggle'
import Home from './pages/Home'

function initialLanguage(): Language {
  try {
    return localStorage.getItem('ett-lang') === 'hi' ? 'hi' : 'en'
  } catch {
    return 'en'
  }
}

export default function App() {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  const t = strings(language)

  function changeLanguage(lang: Language) {
    setLanguage(lang)
    try {
      localStorage.setItem('ett-lang', lang)
    } catch {
      // storage can be unavailable; the choice just will not persist
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1 className="title">Explain This Thing</h1>
          <p className="subtitle">{t.subtitle}</p>
        </div>
        <LanguageToggle language={language} onChange={changeLanguage} />
      </header>
      <Home language={language} />
    </div>
  )
}
