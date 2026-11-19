# Model training plan — deliberately not claiming trained artifacts

A reproducible research model requires actual paired satellite imagery and best-track labels. This project currently includes a real-data import path for IBTrACS, but not a bundled trained neural network.

Recommended experiments:
- Image task: CNN/ResNet classifier on quality-controlled, time-matched geostationary IR/WV image patches.
- Track task: persistence and climatology baselines first; then LSTM/GRU/Temporal CNN on storm-relative sequences.
- Intensity task: gradient boosting or temporal neural model using wind, pressure and environmental predictors.

Split by storm ID (not random image frames) to avoid leakage. Report metrics by forecast lead time and basin, confidence intervals, sample counts, and comparisons with baselines.
