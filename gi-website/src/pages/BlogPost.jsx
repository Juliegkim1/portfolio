import { useParams, Link, Navigate } from 'react-router-dom'
import { posts } from '../data/blogPosts'
import styles from './BlogPost.module.css'

export default function BlogPost() {
  const { slug } = useParams()
  const post = posts.find(p => p.slug === slug)

  if (!post) return <Navigate to="/blog" replace />

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <Link to="/blog" className={styles.back}>← Back to Blog</Link>

        <header className={styles.header}>
          <div className={styles.meta}>
            <span className={styles.category}>{post.category}</span>
            <span className={styles.date}>{formatDate(post.date)}</span>
          </div>
          <h1 className={styles.title}>{post.title}</h1>
        </header>

        <article className={styles.content}>
          {renderContent(post.content)}
        </article>
      </div>
    </div>
  )
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function renderContent(raw) {
  const lines = raw.split('\n')
  const elements = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.startsWith('## ')) {
      elements.push(<h2 key={i} className={styles.h2}>{line.slice(3)}</h2>)
    } else if (line.startsWith('**') && line.endsWith('**')) {
      elements.push(<p key={i} className={styles.bold}>{line.slice(2, -2)}</p>)
    } else if (line.startsWith('- ')) {
      const items = []
      while (i < lines.length && lines[i].startsWith('- ')) {
        items.push(<li key={i}>{lines[i].slice(2)}</li>)
        i++
      }
      elements.push(<ul key={`ul-${i}`} className={styles.ul}>{items}</ul>)
      continue
    } else if (line.trim() !== '') {
      elements.push(<p key={i} className={styles.p}>{line}</p>)
    }

    i++
  }

  return elements
}
