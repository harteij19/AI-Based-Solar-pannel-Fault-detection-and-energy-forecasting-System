# Machine Learning

This directory will contain ML models for:

1. **Energy Forecasting** — Predicting future solar energy generation based on historical sensor data.
2. **Anomaly / Fault Detection** — Identifying unusual patterns that may indicate a fault in the solar panel.

## Status

🚧 **Not yet started.** ML work will begin after sufficient sensor data has been collected.

## Candidate Models

| Task | Models Under Consideration |
|------|---------------------------|
| Energy Forecasting | LSTM, Prophet |
| Anomaly Detection | Isolation Forest, Autoencoder |

## Planned Structure

```
ml/
├── README.md
├── notebooks/             ← Jupyter notebooks for exploration
├── models/                ← Trained model files
├── training/              ← Training scripts
└── evaluation/            ← Evaluation metrics and results
```

## Dependencies (Planned)

- Python 3.x
- `numpy`, `pandas`
- `scikit-learn`
- `tensorflow` or `pytorch`
- `prophet`
- `matplotlib`, `seaborn`
