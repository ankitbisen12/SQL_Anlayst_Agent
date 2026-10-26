import { BarChart3, DollarSign, Lock, MapPin, ShieldCheck, Sparkles, Star, TrendingUp, Trophy, Users } from 'lucide-react'

const SUGGESTIONS = [
  { Icon: DollarSign, tag: 'Pricing', question: 'What is the average nightly price per room type?' },
  { Icon: TrendingUp, tag: 'Trends', question: 'How many bookings had a check-in in each month of 2024?' },
  { Icon: Trophy, tag: 'Rankings', question: 'Which 5 neighbourhoods have the most listings?' },
  { Icon: BarChart3, tag: 'Payments', question: 'What share of bookings used each payment method?' },
  { Icon: MapPin, tag: 'Cities', question: 'Total revenue from completed bookings per city' },
  { Icon: Users, tag: 'Guests', question: 'How many guests come from each country?' },
]

export default function Welcome({ onAsk, disabled }) {
  return (
    <section className="welcome">
      <div className="welcome-badge">
        <Sparkles size={14} aria-hidden="true" />
        AI analyst for your Airbnb database
      </div>
      <h1>What would you like to know?</h1>
      <p className="welcome-sub">
        Ask in plain English. You'll get an answer, a chart or table, and the SQL behind it.
      </p>

      <div className="suggestions">
        {SUGGESTIONS.map(({ Icon, tag, question }) => (
          <button key={question} type="button" className="suggestion" onClick={() => onAsk(question)} disabled={disabled}>
            <span className="suggestion-icon"><Icon size={16} aria-hidden="true" /></span>
            <span className="suggestion-text">
              <span className="suggestion-tag">{tag}</span>
              {question}
            </span>
          </button>
        ))}
      </div>

      <ul className="trust">
        <li><Lock size={14} aria-hidden="true" /> Read-only access</li>
        <li><ShieldCheck size={14} aria-hidden="true" /> Personal data is masked</li>
        <li><Star size={14} aria-hidden="true" /> Answers are based on the data shown</li>
      </ul>
    </section>
  )
}
