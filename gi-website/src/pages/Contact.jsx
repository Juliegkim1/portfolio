import { useState } from 'react'
import styles from './Contact.module.css'

// Paste your deployed Apps Script Web App URL here after setup
const APPS_SCRIPT_URL = import.meta.env.VITE_APPS_SCRIPT_URL || ''

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' })
  const [status, setStatus] = useState('idle') // idle | loading | success | error

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('loading')

    try {
      await fetch(APPS_SCRIPT_URL, {
        method: 'POST',
        mode: 'no-cors', // Apps Script redirects cause CORS errors; no-cors lets the request through
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify({
          ...form,
          timestamp: new Date().toISOString(),
        }),
      })
      // no-cors responses are opaque — we can't read status, so assume success
      setStatus('success')
      setForm({ name: '', email: '', subject: '', message: '' })
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>Get in Touch</h1>
          <p className={styles.subtitle}>
            Have a project in mind, want to collaborate, or just want to connect?
            I'd love to hear from you.
          </p>
        </header>

        <div className={styles.layout}>
          {/* ── Contact Info ── */}
          <aside className={styles.info}>
            <div className={styles.infoCard}>
              {[
                {
                  icon: '✉',
                  label: 'Email',
                  value: 'juliegkim1@gmail.com',
                  href: 'mailto:juliegkim1@gmail.com',
                },
                {
                  icon: '💼',
                  label: 'LinkedIn',
                  value: 'linkedin.com/in/julie-gi-kim-71430513/',
                  href: 'https://www.linkedin.com/in/julie-gi-kim-71430513/',
                },
                {
                  icon: '📍',
                  label: 'Location',
                  value: 'San Francisco, CA',
                  href: null,
                },
              ].map(item => (
                <div key={item.label} className={styles.infoRow}>
                  <span className={styles.infoIcon}>{item.icon}</span>
                  <div>
                    <p className={styles.infoLabel}>{item.label}</p>
                    {item.href ? (
                      <a href={item.href} className={styles.infoValue} target="_blank" rel="noreferrer">
                        {item.value}
                      </a>
                    ) : (
                      <p className={styles.infoValue}>{item.value}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className={styles.availability}>
              <span className={styles.availDot} />
              <p className={styles.availText}>
                Open to consulting, advisory, and collaboration opportunities.
              </p>
            </div>
          </aside>

          {/* ── Message Form ── */}
          <div className={styles.formWrap}>
            <h2 className={styles.formTitle}>Send a Message</h2>

            {status === 'success' ? (
              <div className={styles.successBox}>
                <span className={styles.successIcon}>✓</span>
                <div>
                  <p className={styles.successHeading}>Message received!</p>
                  <p className={styles.successSub}>
                    Thanks for reaching out. I'll get back to you soon.
                  </p>
                </div>
                <button className={styles.resetBtn} onClick={() => setStatus('idle')}>
                  Send another
                </button>
              </div>
            ) : (
              <form className={styles.form} onSubmit={handleSubmit} noValidate>
                <div className={styles.row}>
                  <div className={styles.field}>
                    <label htmlFor="name" className={styles.label}>Name <span className={styles.req}>*</span></label>
                    <input
                      id="name"
                      name="name"
                      type="text"
                      required
                      className={styles.input}
                      placeholder="Your full name"
                      value={form.name}
                      onChange={handleChange}
                      disabled={status === 'loading'}
                    />
                  </div>
                  <div className={styles.field}>
                    <label htmlFor="email" className={styles.label}>Email <span className={styles.req}>*</span></label>
                    <input
                      id="email"
                      name="email"
                      type="email"
                      required
                      className={styles.input}
                      placeholder="you@example.com"
                      value={form.email}
                      onChange={handleChange}
                      disabled={status === 'loading'}
                    />
                  </div>
                </div>

                <div className={styles.field}>
                  <label htmlFor="subject" className={styles.label}>Subject</label>
                  <input
                    id="subject"
                    name="subject"
                    type="text"
                    className={styles.input}
                    placeholder="What's this about?"
                    value={form.subject}
                    onChange={handleChange}
                    disabled={status === 'loading'}
                  />
                </div>

                <div className={styles.field}>
                  <label htmlFor="message" className={styles.label}>Message <span className={styles.req}>*</span></label>
                  <textarea
                    id="message"
                    name="message"
                    required
                    rows={6}
                    className={styles.textarea}
                    placeholder="Tell me about your project, question, or idea..."
                    value={form.message}
                    onChange={handleChange}
                    disabled={status === 'loading'}
                  />
                </div>

                {status === 'error' && (
                  <p className={styles.errorMsg}>
                    Something went wrong. Please try again or email me directly.
                  </p>
                )}

                <button
                  type="submit"
                  className={styles.submit}
                  disabled={status === 'loading'}
                >
                  {status === 'loading' ? 'Sending...' : 'Send Message'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
