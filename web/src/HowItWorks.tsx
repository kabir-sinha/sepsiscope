// "How it works": headline numbers, the pipeline in four steps, why an unseen hospital
// matters, and a glossary.
import { DIRS, NAMES, rowsFor, useResults } from './resultsData'
const STEPS = [
  {
    title: 'Hourly vitals and labs',
    text: 'Every ICU hour brings new measurements: heart rate, breathing, temperature, blood pressure, oxygen and lab tests.',
    icon: 'M6 30 L14 18 L20 24 L28 10 L36 22',
  },
  {
    title: 'A risk every hour',
    text: 'The model reads only what is known so far (never the future) and gives a sepsis risk for that hour.',
    icon: 'M6 32 L6 8 M6 32 L38 32 M10 28 L18 24 L26 20 L34 12',
  },
  {
    title: 'Alert above a threshold',
    text: 'The threshold is chosen on the training hospital so that only about 5 % of patient-hours raise an alert.',
    icon: 'M4 18 L40 18 M10 26 L18 22 L24 12 L32 24',
  },
  {
    title: 'Reasons shown',
    text: 'Each alert lists the five measurements that pushed the risk up or down the most, in plain English.',
    icon: 'M8 10 L30 10 M8 18 L24 18 M8 26 L34 26',
  },
]

const GLOSSARY: [string, string][] = [
  ['Sepsis', "A life-threatening reaction to infection, where the body's response damages its own organs. Every hour of delay in treatment matters."],
  ['Onset', 'The hour sepsis is recorded as starting. In this dataset it is 6 hours after the first hour labelled septic.'],
  ['Early-warning window', 'The 12 hours before onset, up to and including the onset hour. An alert here counts as a timely warning.'],
  ['NEWS2', "The UK's National Early Warning Score: points for abnormal vitals, added up. Here a modified version without the consciousness item (maximum 17)."],
  ['False alarm', 'An alert for a patient who never develops sepsis. Too many alarms cause alarm fatigue, so alerts are targeted at about 5 % of hours at the training hospital.'],
  ['Unseen hospital', 'A hospital whose patients were never used to train, tune or set the threshold of the model. All demo patients come from one.'],
]

function Headline() {
  const [doc] = useResults()
  if (!doc) return null
  return (
    <section className="panel headline" aria-labelledby="headline-title">
      <h2 id="headline-title">Headline results on the unseen hospital</h2>
      <p className="help">From the committed result files; utility 1 = perfect, 0 = never alerting. AUROC 0.5 = chance.</p>
      <div className="strip">
        {Object.entries(DIRS).map(([d, title]) => (
          <div key={d} className="strip-group">
            <h3>{title}</h3>
            <dl>
              {rowsFor(doc, d)
                .filter((r) => ['lgbm', 'lr', 'news2'].includes(r.model))
                .map((r) => (
                  <div key={r.model} className="stat">
                    <dt>
                      {NAMES[r.model]}
                      {r.model === 'lgbm' && ' (headline)'}
                    </dt>
                    <dd className="num">
                      utility <strong>{r.utility.toFixed(3)}</strong> · AUROC <strong>{r.auroc.toFixed(3)}</strong>
                    </dd>
                  </div>
                ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  )
}

export function HowItWorks() {
  return (
    <div className="how">
      <Headline />
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s.title} className="step">
            <svg viewBox="0 0 44 40" width="56" height="50" aria-hidden="true">
              <path d={s.icon} fill="none" stroke="var(--risk)" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <span className="step-n">Step {i + 1}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </li>
        ))}
      </ol>
      <section className="panel">
        <h2>Why test on an unseen hospital?</h2>
        <p>
          Hospitals differ in their patients, equipment and how often staff take measurements. A model
          can learn those habits instead of the illness and look excellent at home, then fail
          elsewhere. So SepsiScope is always trained on one hospital and judged on the other, with
          nothing from the second hospital used for training, tuning or the alert threshold. The
          numbers on the Results tab are honest estimates of how it would behave in a new hospital,
          including where it falls short.
        </p>
      </section>
      <section className="panel">
        <h2>Glossary</h2>
        <dl className="glossary">
          {GLOSSARY.map(([term, text]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  )
}
