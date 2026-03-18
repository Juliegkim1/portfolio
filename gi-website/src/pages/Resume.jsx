import styles from './Resume.module.css'

const experience = [
  {
    company: 'Deloitte Technology (DT) Office of CIO',
    title: 'OCIO Analytics Program Lead and Data Solution Architect',
    period: 'March 2022 – January 2026',
    location: 'San Francisco, CA',
    bullets: [
      'Orchestrate the Office of CIO Analytics Program, establishing DataOps and AIOps frameworks to enhance strategic alignment and data product development efficiency, and lead the product strategy and development of program standard operating procedures and workflows for all OCIO analytics products.',
      'Guide diverse technical teams in designing, developing, and delivering innovative analytics data products (custom web applications, GCP Diagflow Chatbot Agent, PowerBI, Looker, and Tableau dashboards), integrating data engineering, AI engineering, and human-centered design principles.',
      'Architect and implement enterprise solutions with generative AI models (Gemini and GPT), managing critical vendor relationships and ensuring compliance with DT Secure SDLC and AI & Data governance.',
      'Build and optimize complex Python-driven data pipelines and products for critical enterprise needs in cyber analytics, IT asset management, regulatory compliance, cloud financial operations, and billing, leveraging GCP DataProc, BigQuery, and Cloud Storage.',
      'Provide deep technical consulting for enterprise AI adoption across divisions, acting as a trusted advisor in AI-transformation programs to ensure data availability and seamless system integration for timely delivery.',
    ],
  },
  {
    company: 'Logic2020',
    title: 'Senior Manager',
    period: 'October 2021 – March 2022',
    location: 'San Francisco, CA',
    bullets: [
      'Directed the end-to-end technical overhaul for public health valuation analytics at the Bill & Melinda Gates Foundation, architecting and deploying next-generation data pipelines and analytical platforms that significantly enhanced portfolio management insights.',
      'Translated complex business objectives into actionable technical requirements and solution roadmaps for Kaiser Permanente through facilitated Design Thinking workshops, ensuring strategic alignment for data product development.',
      'Crafted detailed analytics roadmaps and proposals, articulating the technical vision and phased implementation strategy for data products to executive stakeholders and potential clients, supporting business development with proposals and solution approaches.',
      'Oversaw cross-functional teams in engineering highly secure and compliant data solutions for PG&E, tackling challenges in data governance, lineage, and automated reporting to meet regulatory standards.',
    ],
  },
  {
    company: 'Loyola Marymount University',
    title: 'Consultant Researcher, NSF Convergence Accelerator Track E',
    period: 'October 2021 – September 2022',
    location: 'Oakland, CA',
    bullets: [
      'Coordinated the technical implementation and deployment of a computer vision solution for distinct octopus species prediction (from image/video data) by the Machine Learning team, utilizing CNN and DNN models.',
      'Developed and launched user-centric dashboards and applications (Python/Django) for ML teams, integrating Human-Centered Design to visualize model results and insights effectively, and operationalized core ML models on Google Cloud Platform (GCP), ensuring high scalability and efficiency for inference and data processing.',
    ],
  },
  {
    company: 'The Permanente Medical Group (TPMG)',
    title: 'Consulting Manager',
    period: 'February 2021 – September 2021',
    location: 'Oakland, CA',
    bullets: [
      'Initiated and led the NCAL OR Data Governance Committee, establishing comprehensive data standards and unifying metrics across Performance Improvement. Developed a suite of 10+ advanced financial and operational dashboards, including for the Regional Perioperative Medicine Core Program, Senior Surgical Care Program, and Regional Surgical Site Infections Committee.',
      'Led diverse cross-functional teams in the technical implementation and integration of advanced performance improvement analytics solutions, driving data-driven initiatives to enhance operational efficiency and patient outcomes through implementing data quality control processes, standardizing data intake, integrating disparate data sources for a holistic view, and championing user-centric dashboard design using the Human-Centered Design Thinking method.',
    ],
  },
  {
    company: 'Logic2020',
    title: 'Analytics Manager',
    period: 'December 2020 – February 2021',
    location: 'San Francisco, CA',
    bullets: [
      'Planned and executed the T-Mobile AI Chatbot Performance & Transition Analytics project, leading a cross-functional team to design and deliver critical dashboards that provided actionable insights, enabling data-driven optimization of customer experience and agent efficiency.',
      'Drove end-to-end project lifecycle, from strategic planning and requirements definition to execution and delivery, consistently exceeding service level agreements and proactively mitigating risks to ensure on-time, on-budget completion.',
    ],
  },
  {
    company: 'Deloitte Consulting, LLC',
    title: 'Strategy & Analytics Manager',
    period: 'January 2019 – December 2020',
    location: 'Arlington, VA',
    bullets: [
      'Defined and executed a comprehensive enterprise-wide data asset management strategy, significantly improving data governance, discoverability, and utility across multiple business units.',
      'Led technical teams in implementing cutting-edge cloud analytics solutions for a top-tier banking client, enabling data-driven decision-making and optimizing key business processes.',
    ],
  },
  {
    company: 'Ernst & Young, LLC',
    title: 'Advisory Data Analytics Senior',
    period: 'April 2018 – January 2019',
    location: 'McLean, VA',
    bullets: [
      'Bridged the gap between business and technology by analyzing complex business analytics challenges within the Department of Defense (DoD) enterprise transaction systems and translating them into actionable technical solutions through expertise in data management and visualization.',
      'Led the Data Team in building business intelligence and analytics solutions to automate reconciliation and compliance testing, significantly supporting the DoD\'s critical audit readiness mission.',
    ],
  },
  {
    company: 'Deloitte Consulting, LLC',
    title: 'Senior Technology Consultant & Data Scientist',
    period: 'March 2015 – April 2018',
    location: 'Arlington, VA',
    bullets: [
      'Led enterprise data migration and analytics projects for federal clients (DoD, HHS, DHS), focusing on SQL server migration, advanced data analytics solutions, enterprise resource planning, and contract management.',
      'Developed NLP classification models for NIH and designed/delivered Tableau and Design Thinking training, empowering data analysis and visualization best practices.',
    ],
  },
  {
    company: 'The Lewin Group',
    title: 'Research Consultant',
    period: 'June 2014 – March 2015',
    location: 'Fairfax, VA',
    bullets: [
      'Served as data visualization consultant for Medicaid Beneficiary Insights in State Consulting (Montana, Vermont, Rhode Island) and developed data pipelines and visualizations.',
    ],
  },
  {
    company: 'The Johns Hopkins University',
    title: 'Multiple Roles',
    period: 'June 2011 – June 2014',
    location: 'Baltimore, MD',
    bullets: [
      'Armstrong Institute of Patient Quality and Safety — Visual Analytics Specialist (Dec 2013 – Jun 2014): Coordinated analytical initiatives across Johns Hopkins Medicine and developed effective methods and tools for tracking clinical quality and financial outcomes using SAP Business Objects.',
      'Sidney Kimmel Comprehensive Cancer Center — Financial Analyst (Jun 2012 – Dec 2013): Served as Medical Oncology Department Financial & Grant Management Lead, managing departmental budget and leading grant application processes.',
      'Institute of Clinical Translational Research — Interim Financial Manager (Jun 2011 – Dec 2012): Analyzed financial reports across research funding sources, identified budget adjustment opportunities, and partnered with program directors on grant administration.',
    ],
  },
]

const education = [
  {
    school: 'Johns Hopkins University, Krieger School of Arts & Science',
    degree: 'MS in Applied Economics',
    year: 'December 2014',
    location: 'Baltimore, MD',
  },
  {
    school: 'University of Maryland Baltimore County',
    degree: 'Bachelor of Science in Financial Economics',
    year: 'May 2012',
    location: 'Baltimore, MD',
  },
]

const awards = [
  { title: 'Deloitte Outstanding Performance Award', date: '05/2024' },
  { title: 'Deloitte Applause Awards', date: '02/2020, 08/2017, 08/2016, 02/2016, 10/2015, 05/2024' },
  { title: 'Ernst & Young Living Our Values and Bravo Awards', date: '10/2018, 08/2018, 07/2018' },
  { title: 'Deloitte National Recognition for Technology (R4T) Award', date: '01/2017' },
]

const competencies = [
  { label: 'Data Architecture & Engineering', detail: 'Scalable Pipeline Design (ETL/ELT), Data Modeling, Data Governance, Real-time Processing' },
  { label: 'Cloud Platforms', detail: 'GCP (BigQuery, Dataflow, Vertex AI) · AWS (EC2, S3, Lambda, Glue, SageMaker) · Azure (Data Factory, Synapse)' },
  { label: 'Data Warehousing & Lakehouses', detail: 'Snowflake · Google BigQuery · Amazon Redshift · Databricks · Google BigTable' },
  { label: 'Programming & Scripting', detail: 'Python (Pandas, PySpark, ML Libraries) · SQL (Advanced) · JavaScript · HTML5 · CSS' },
  { label: 'AI/ML & Generative AI', detail: 'Gemini · GPT · Claude · MLOps · GenAI & Agentic AI Systems · AI Operating Models' },
  { label: 'Data Visualization & BI', detail: 'Tableau · Google Looker · Microsoft Power BI · Amazon QuickSight · SAP Business Objects' },
  { label: 'Databases', detail: 'PostgreSQL · Microsoft SQL Server · BigQuery · SAP BW' },
  { label: 'Enterprise Platforms', detail: 'ServiceNow · SAP' },
  { label: 'Leadership & Strategy', detail: 'Technical Product Strategy · Team Leadership · Agile · AI Adoption · Business Development' },
  { label: 'Process Engineering', detail: 'Lean Six Sigma Yellow Belt' },
]

export default function Resume() {
  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.hero}>
        <div className={styles.heroInner}>
          <span className={styles.eyebrow}>Resume</span>
          <h1 className={styles.name}>Gi Kim</h1>
          <p className={styles.tagline}>
            Data Analytics Engineer &amp; Program Leader · San Francisco, CA
          </p>
          <div className={styles.contact}>
            <a href="mailto:juliegkim1@gmail.com" className={styles.contactLink}>juliegkim1@gmail.com</a>
            <span className={styles.dot}>·</span>
            <a href="https://www.linkedin.com/in/julie-gi-kim-71430513/" target="_blank" rel="noreferrer" className={styles.contactLink}>LinkedIn</a>
          </div>
        </div>
      </header>

      <div className={styles.container}>

        {/* Summary */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Summary</h2>
          <p className={styles.summary}>
            Experienced data analytics engineer and program leader with 10+ years of proven success in leading
            technical teams and driving data solution adoption across enterprise organizations. Expert in translating
            complex analytics and cloud data platform capabilities into compelling business value propositions that
            accelerate customer decision-making. Excels at coaching technical talent, developing go-to-market
            strategies, and collaborating cross-functionally to deliver customer-centric solutions that optimize
            organizational performance and unlock new opportunities through data-driven insights.
          </p>
        </section>

        {/* Core Competencies */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Core Competencies</h2>
          <div className={styles.competencyGrid}>
            {competencies.map(c => (
              <div key={c.label} className={styles.competencyCard}>
                <p className={styles.competencyLabel}>{c.label}</p>
                <p className={styles.competencyDetail}>{c.detail}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Experience */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Experience</h2>
          <div className={styles.timeline}>
            {experience.map((job, i) => (
              <div key={i} className={styles.job}>
                <div className={styles.jobMeta}>
                  <p className={styles.jobPeriod}>{job.period}</p>
                  <p className={styles.jobLocation}>{job.location}</p>
                </div>
                <div className={styles.jobContent}>
                  <p className={styles.jobCompany}>{job.company}</p>
                  <p className={styles.jobTitle}>{job.title}</p>
                  <ul className={styles.jobBullets}>
                    {job.bullets.map((b, j) => (
                      <li key={j}>{b}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Education */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Education</h2>
          <div className={styles.eduGrid}>
            {education.map(e => (
              <div key={e.degree} className={styles.eduCard}>
                <p className={styles.eduDegree}>{e.degree}</p>
                <p className={styles.eduSchool}>{e.school}</p>
                <p className={styles.eduMeta}>{e.year} · {e.location}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Awards */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Awards &amp; Recognition</h2>
          <div className={styles.awardsList}>
            {awards.map(a => (
              <div key={a.title} className={styles.award}>
                <p className={styles.awardTitle}>{a.title}</p>
                <p className={styles.awardDate}>{a.date}</p>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  )
}
