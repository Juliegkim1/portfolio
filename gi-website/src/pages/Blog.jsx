import { Link } from 'react-router-dom'
import { posts } from '../data/blogPosts'
import styles from './Blog.module.css'

export default function Blog() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>Blog</h1>
          <p className={styles.subtitle}>
            Thoughts on engineering, design, and building things that matter.
          </p>
        </header>

        <div className={styles.list}>
          {posts.map(post => (
            <Link key={post.slug} to={`/blog/${post.slug}`} className={styles.card}>
              <div className={styles.cardMeta}>
                <span className={styles.category}>{post.category}</span>
                <span className={styles.date}>{formatDate(post.date)}</span>
              </div>
              <h2 className={styles.cardTitle}>{post.title}</h2>
              <p className={styles.cardExcerpt}>{post.excerpt}</p>
              <span className={styles.readMore}>Read more →</span>
            </Link>
          ))}
        </div>
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
