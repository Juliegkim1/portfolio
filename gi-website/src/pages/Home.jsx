import { Link } from 'react-router-dom'
import styles from './Home.module.css'

export default function Home() {
  return (
    <div className={styles.page}>
      <div className={styles.layout}>

        {/* ── Left: Photo ── */}
        <aside className={styles.photoCol}>
          <div className={styles.photoSticky}>
            <div className={styles.photoFrame}>
              <img src="/profile.jpg" alt="Gi Kim" className={styles.photo} />
            </div>
            <div className={styles.blob1} aria-hidden="true" />
            <div className={styles.blob2} aria-hidden="true" />
          </div>
        </aside>

        {/* ── Right: All content ── */}
        <main className={styles.contentCol}>

          {/* Hero */}
          <section className={styles.hero}>
            <span className={styles.greeting}>Data Analytics Engineer &amp; Program Leader</span>
            <h1 className={styles.name}>Gi Kim</h1>
            <p className={styles.tagline}>
              10+ years turning complex data into decisions that matter — from enterprise
              AI systems at Deloitte to cloud data platforms serving healthcare, finance,
              and the public sector.
            </p>
            <div className={styles.heroCta}>
              <Link to="/portfolio" className={styles.btnPrimary}>View My Work</Link>
              <Link to="/contact" className={styles.btnSecondary}>Get in Touch</Link>
            </div>
          </section>

          <hr className={styles.divider} />

          {/* About */}
          <section className={styles.about}>
            <h2 className={styles.sectionTitle}>About Me</h2>
            <div className={styles.aboutText}>
              <p>
                I'm a data analytics engineer and program leader with a decade of experience
                bridging technical depth and strategic vision. Currently at Deloitte Technology,
                I lead the Office of CIO Analytics Program — architecting cloud data platforms,
                generative AI solutions, and DataOps frameworks that drive decisions across the enterprise.
              </p>
              <p>
                My work spans GCP, AWS, and Azure; Python pipelines and BigQuery lakehouses;
                Gemini and GPT integrations; and everything in between. I've delivered for
                Kaiser Permanente, the Bill &amp; Melinda Gates Foundation, T-Mobile, PG&E,
                and federal agencies including the DoD, HHS, and DHS.
              </p>
              <p>
                I hold an MS in Applied Economics from Johns Hopkins and a BS in Financial Economics
                from UMBC — a background that keeps me grounded in the "so what" behind the data.
              </p>
            </div>
            <div className={styles.aboutCards}>
              {[
                { icon: '☁', title: 'Cloud & Data Engineering', desc: 'GCP · AWS · Azure · BigQuery · Snowflake · Dataflow · ETL/ELT pipelines' },
                { icon: '✦', title: 'AI & Generative AI', desc: 'Gemini · GPT · Claude · MLOps · Agentic AI systems · Vertex AI' },
                { icon: '◈', title: 'Leadership & Strategy', desc: 'Program management · DataOps · Human-centered design · Cross-functional teams' },
              ].map(card => (
                <div key={card.title} className={styles.card}>
                  <span className={styles.cardIcon}>{card.icon}</span>
                  <h3 className={styles.cardTitle}>{card.title}</h3>
                  <p className={styles.cardDesc}>{card.desc}</p>
                </div>
              ))}
            </div>
          </section>

          <hr className={styles.divider} />

          {/* Skills */}
          <section className={styles.skills}>
            <h2 className={styles.sectionTitle}>Skills &amp; Tools</h2>
            <div className={styles.skillGrid}>
              {[
                'Python', 'SQL', 'JavaScript', 'PySpark',
                'Google Cloud Platform', 'AWS', 'Azure', 'BigQuery',
                'Snowflake', 'Databricks', 'Vertex AI', 'Dataflow',
                'Tableau', 'Looker', 'Power BI', 'Generative AI',
                'PostgreSQL', 'ServiceNow', 'SAP', 'Lean Six Sigma',
              ].map(skill => (
                <span key={skill} className={styles.skillTag}>{skill}</span>
              ))}
            </div>
          </section>

        </main>
      </div>
    </div>
  )
}
