# Model card (stub)

_Filled in after training (later phase). Structure follows
[Mitchell et al. 2019, "Model Cards for Model Reporting"](https://doi.org/10.1145/3287560.3287596)._

- **Model details:** _TBD_ (LightGBM, saved as text + `feature_schema.json`)
- **Intended use:** research and teaching only. **Not for clinical use.**
- **Out-of-scope uses:** any real patient decision.
- **Training data:** PhysioNet/CinC 2019, hospital A or B (see `docs/protocol.md`).
- **Evaluation data:** the other hospital (external validation).
- **Metrics:** as frozen in `docs/protocol.md`; official normalized utility is the reference.
- **Subgroups:** sex, age < 65 / >= 65.
- **Ethical considerations and caveats:** _TBD_
