import { ArrowRight, CalendarDays, FileText, ShieldCheck, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import heroArt from './assets/academic-ai-hero-v2.png'

const capabilities = [
  { icon: FileText, title: 'Understand every circular', body: 'Upload a notice and turn dense academic language into an evidence-grounded summary.' },
  { icon: Sparkles, title: 'Ask with context', body: 'Explore a temporary circular with AI answers that point back to the relevant source.' },
  { icon: CalendarDays, title: 'Never miss a deadline', body: 'Keep verified actions, payments, and academic dates in one focused workspace.' },
]

export default function PublicHome() {
  return <main className="public-page">
    <nav className="public-nav" aria-label="Public navigation">
      <Link className="public-logo" to="/"><span className="brand-mark"><Sparkles size={16}/></span><span>CircularLens <em>AI</em></span></Link>
      <div className="public-nav-actions"><Link className="quiet-link" to="/login">Sign in</Link><Link className="primary compact" to="/register">Create account <ArrowRight size={15}/></Link></div>
    </nav>
    <section className="hero hero-layout">
      <div className="hero-copy">
        <p className="eyebrow"><span/> Academic intelligence, made practical</p>
        <h1>Turn University Circulars Into Smart Actions.</h1>
        <p className="hero-lead">CircularLens AI reads university circulars, surfaces the actions that matter, and keeps supporting evidence close at hand.</p>
        <div className="hero-actions"><Link className="primary" to="/register">Start your workspace <ArrowRight size={17}/></Link><Link className="guest-button" to="/guest"><Sparkles size={17}/> Continue as guest</Link></div>
        <p className="hero-note"><ShieldCheck size={15}/> Guest analysis is temporary. Your documents and reminders stay private.</p>
      </div>
      <div className="hero-art" aria-label="Futuristic academic document intelligence illustration"><img src={heroArt} alt="Abstract academic documents illuminated by AI intelligence"/></div>
    </section>
    <section className="feature-grid" aria-label="CircularLens AI capabilities">
      {capabilities.map(({ icon: Icon, title, body }) => <article className="feature-card" key={title}><span className="feature-icon"><Icon size={19}/></span><div><h2>{title}</h2><p>{body}</p></div></article>)}
    </section>
    <section className="how-it-works"><div><p className="eyebrow">HOW IT WORKS</p><h2>From circular to confident next step.</h2></div><ol><li><b>1</b><span><strong>Add a circular</strong><small>Upload a supported document or paste official text.</small></span></li><li><b>2</b><span><strong>Review the evidence</strong><small>See summaries, extracted requirements, and source passages.</small></span></li><li><b>3</b><span><strong>Act with context</strong><small>Track relevant tasks without treating AI suggestions as confirmed facts.</small></span></li></ol></section>
    <footer className="public-footer"><span>© CircularLens AI</span><span>Evidence-grounded academic decision support</span></footer>
  </main>
}
