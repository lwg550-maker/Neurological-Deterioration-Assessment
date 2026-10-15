# Frozen M1 Research-Use Inference Tool v1.0.0

This first frozen public release contains:

- the complete frozen M1 model specification and preprocessing rules;
- the exact alert threshold `0.028094640664533963`;
- a standalone local browser calculator and GitHub Pages source;
- a Python reference implementation that performs inference only;
- a synthetic worked example with archived expected output;
- a 1,000-anchor numerical reproduction audit (maximum absolute error `1.1102230246251565e-16`); and
- automated Python and browser-calculator parity tests.

No MIMIC-IV or eICU-CRD patient-level data are included.

This is a research-use prototype and dynamic prioritization tool for repeat neurological assessment. It is not a prospectively validated clinical decision-support system and does not directly guide CT, medication, EVD, surgery, or other intervention.
