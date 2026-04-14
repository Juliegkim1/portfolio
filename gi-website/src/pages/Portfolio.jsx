import styles from './Portfolio.module.css'

const projects = [
  {
    id: 1,
    title: 'Cabrera Construction',
    description:
      'Full business website for a Bay Area residential construction and remodeling company operating since 2012. Features service showcases for custom home builds, kitchen & bath remodels, ADUs, and additions — with contact forms and mobile-responsive design.',
    tags: ['Web Design', 'Squarespace', 'Responsive Design', 'Small Business'],
    accent: 'peach',
    link: 'https://www.cabrera.construction/',
    github: '#',
  },
  {
    id: 2,
    title: 'DataNA Solutions',
    description:
      'Business website for DataNA Solutions, a data analytics and consulting firm. Built with a modern, professional design to showcase services and drive client engagement.',
    tags: ['Web Design', 'Wix', 'Responsive Design', 'Analytics'],
    accent: 'sage',
    link: 'https://www.datanasolutions.com',
    github: '#',
  },
  {
    id: 3,
    title: 'iStudy',
    description:
      'An AI-powered study platform that helps students retain information more effectively through spaced repetition and adaptive quizzes.',
    tags: ['Python', 'React', 'FastAPI', 'PostgreSQL'],
    accent: 'rose',
    link: '#',
    github: '#',
  },
  {
    id: 2,
    title: 'Portfolio Website',
    description:
      'This site — a clean, minimal personal portfolio built with React and hosted on Google Cloud Firebase Hosting.',
    tags: ['React', 'Vite', 'CSS Modules', 'Firebase'],
    accent: 'sage',
    link: '#',
    github: 'https://github.com/gikim/portfolio',
  },
  {
    id: 3,
    title: 'Data Pipeline',
    description:
      'End-to-end ETL pipeline processing millions of events daily using Cloud Dataflow and BigQuery with real-time dashboards.',
    tags: ['Python', 'Google Cloud', 'BigQuery', 'Dataflow'],
    accent: 'lavender',
    link: '#',
    github: '#',
  },
  {
    id: 4,
    title: 'ML Classification',
    description:
      'A multi-class text classifier achieving 94% accuracy, deployed as a REST API serving real-time predictions.',
    tags: ['TensorFlow', 'FastAPI', 'Docker', 'GCP'],
    accent: 'peach',
    link: '#',
    github: '#',
  },
]

const accentMap = {
  rose: 'var(--accent-rose)',
  sage: 'var(--accent-sage)',
  lavender: 'var(--accent-lavender)',
  peach: 'var(--accent-peach)',
}

export default function Portfolio() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>Portfolio</h1>
          <p className={styles.subtitle}>
            A selection of projects I've built — from side experiments to production systems.
          </p>
        </header>

        <div className={styles.grid}>
          {projects.map(project => (
            <article
              key={project.id}
              className={styles.card}
              style={{ '--card-accent': accentMap[project.accent] }}
            >
              <div className={styles.cardAccentBar} />
              <div className={styles.cardBody}>
                <h2 className={styles.cardTitle}>{project.title}</h2>
                <p className={styles.cardDesc}>{project.description}</p>
                <div className={styles.tags}>
                  {project.tags.map(tag => (
                    <span key={tag} className={styles.tag}>{tag}</span>
                  ))}
                </div>
                <div className={styles.cardLinks}>
                  {project.link !== '#' && (
                    <a href={project.link} className={styles.linkBtn} target="_blank" rel="noreferrer">
                      Live Demo ↗
                    </a>
                  )}
                  {project.github !== '#' && (
                    <a href={project.github} className={styles.linkGhost} target="_blank" rel="noreferrer">
                      GitHub ↗
                    </a>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
