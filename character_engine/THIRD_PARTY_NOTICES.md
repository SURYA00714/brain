# THIRD-PARTY ARCHITECTURAL NOTICES & REFERENCES

This document details third-party projects and repositories studied as architectural, algorithmic, and behavioral references for the AO Living Desktop Companion, in accordance with Section 52 and Section 53 of the AO Master Specification.

---

### 1. Hanami
- **Source / Repository**: https://github.com/Undi95/Hanami
- **License**: MIT / Apache-2.0 derivative
- **Components Studied**:
  - Humanoid state machine and transition graph topology (165 states, legal transition graph patterns).
  - Joint limits and anatomical rotation bounding concepts.
  - Gaze, saccades, and natural eye fixation timing.
- **Modification Status**: Clean-room implementation in JavaScript. No external assets directly copied.
- **Attribution**: Concepts derived from Undi95's Hanami project.

---

### 2. Overte
- **Source / Repository**: https://github.com/overte-org/overte
- **License**: Apache-2.0
- **Components Studied**:
  - Humanoid animation state flow, inverse kinematics constraints, and joint angle bounds.
  - Saccadic eye movement logic.
- **Modification Status**: Clean-room architectural design adapted for Three.js and `@pixiv/three-vrm`.
- **Attribution**: Copyright (c) Overte e.V. and contributors. Licensed under the Apache License, Version 2.0.

---

### 3. Fano VRM Controller
- **Source / Repository**: https://github.com/Fano1/fano-vrm-controller
- **License**: Apache-2.0
- **Components Studied**:
  - Three.js + `@pixiv/three-vrm` bone hierarchy mapping and humanoid access patterns.
  - Expression weight control and blendshape safety rules.
- **Modification Status**: Reference design studied for VRM humanoid bone traversal and clamp application.
- **Attribution**: Copyright (c) Fano1. Licensed under the Apache License, Version 2.0.

---

### 4. Liqu Desktop Companion
- **Source / Repository**: https://github.com/CameronCodesStuff/liqu-companion
- **License**: MIT
- **Components Studied**:
  - Layered procedural micro-motion (thoracic breathing sine waves, gentle weight-shift sway, settle-to-idle pacing).
  - Passive cursor interaction philosophy (no permanent robotic tracking).
- **Modification Status**: Mathematical concepts adapted to AO's AnimationController and LookAtController.
- **Attribution**: Copyright (c) CameronCodesStuff.

---

### 5. ARPA Avatar
- **Source / Repository**: https://github.com/ARPAHLS/avatar
- **License**: MIT
- **Components Studied**:
  - Semantic intention abstraction (dispatching high-level actions rather than direct bone manipulation).
  - VRM expression layering and catalog metadata architecture.
- **Modification Status**: Clean-room semantic ActionIntent dispatching pipeline.
- **Attribution**: ARPA Avatar Project.

---

### 6. Desktop Virtual Buddy
- **Source / Repository**: https://github.com/spyderweb47/Desktop-Virtual-buddy
- **License**: MIT
- **Components Studied**:
  - Desktop world model, safe screen margin clamping, and surface support checking.
  - Priority-driven state transitions with cooldown buffers to prevent repetition.
- **Modification Status**: Mathematical safe area bounds and Utility AI scoring logic adapted for WorldModel and ActivityRegistry.
- **Attribution**: Copyright (c) spyderweb47.
