import { useState } from 'react'
import { Link } from 'react-router-dom'
import { posts } from '../data/blogPosts'
import { linkedinPosts } from '../data/linkedinPosts'
import styles from './Blog.module.css'

const TABS = [
  { id: 'writing', label: 'Writing' },
  { id: 'linkedin', label: 'LinkedIn' },
]

export default function Blog() {
  const [tab, setTab] = useState('writing')

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>Blog</h1>
          <p className={styles.subtitle}>
            Thoughts on data, AI, leadership, and building things that matter.
          </p>
        </header>

        {/* Tab switcher */}
        <div className={styles.tabs}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={tab === t.id ? styles.tabActive : styles.tab}
              onClick={() => setTab(t.id)}
            >
              {t.id === 'linkedin' && <LinkedInIcon />}
              {t.label}
            </button>
          ))}
        </div>

        {/* Writing tab */}
        {tab === 'writing' && (
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
        )}

        {/* LinkedIn tab */}
        {tab === 'linkedin' && (
          <div className={styles.list}>
            {linkedinPosts.map(post => (
              <a
                key={post.id}
                href={post.url}
                target="_blank"
                rel="noreferrer"
                className={styles.card}
              >
                <div className={styles.cardMeta}>
                  <span className={styles.liBadge}>
                    <LinkedInIcon /> LinkedIn
                  </span>
                  <span className={styles.date}>{formatDate(post.date)}</span>
                </div>
                <p className={styles.cardExcerpt}>{post.excerpt}</p>
                <div className={styles.liFooter}>
                  {post.tags.map(tag => (
                    <span key={tag} className={styles.tag}>{tag}</span>
                  ))}
                  <span className={styles.readMore} style={{ marginLeft: 'auto' }}>
                    View on LinkedIn ↗
                  </span>
                </div>
              </a>
            ))}
          </div>
        )}
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

function LinkedInIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}
