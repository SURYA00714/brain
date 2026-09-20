# AO Companion — Third-Party Notices & License Inventory

This document records the origin, original author, license, attribution requirements, modification status, redistribution permissions, and commercial-use status for all external third-party assets and algorithmic references incorporated into AO.

---

## 1. Summary of External Sources

| Source | Category | Primary License | Author / Copyright Holder | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Overte Project** | Animations (`.vrma`) & IK / Math algorithms | Apache License 2.0 | High Fidelity, Inc. (2013-2019), Vircadia contributors (2019-2021), Overte e.V. (2022-2026) | Hand-animated in Maya for humanoid avatars. Converted to VRMA 1.0 format. |
| **Quaternius** | Seated Transitions (`.vrma`) | CC0 1.0 Universal | Quaternius (<https://quaternius.com>) | Public domain. Sit enter and sit exit transitions anchored to VRM rest pose. |
| **Microsoft Rocketbox** | Expressive Emotes & Listening (`.vrma`) | MIT License | Microsoft Corporation (2020) | Retargeted onto VRM 1.0 normalized humanoid rig. |
| **pixiv Inc. VRoid Project** | Motion Pack (`.vrma`) | Custom Permissive (Free BOOTH pack) | pixiv Inc. (2024) | Free 7-motion animation pack. Credit required in public/commercial distributions. |
| **Liqu Desktop Companion** | Procedural Motion & Follow-Through Algorithms | Reference / MIT | CameronCodesStuff (<https://github.com/CameronCodesStuff/liqu-companion>) | Procedural multi-phase breathing, weight-shifting, and quaternion slerp techniques. Bundled model not copied. |
| **ARPA AVATAR** | Local Loopback Agent Bus Architecture | MIT License | ARPA Hellenic Logical Systems (<https://github.com/ARPAHLS/avatar>) | Local HTTP/WebSocket loopback agent bus design routed through ActionIntent. |

---

## 2. Animation Asset Inventory & Rights

| Asset Filename | Category / Role | Source Repository | Original Author / Creator | License | Required Attribution | Modification Status | Redistribution | Commercial Use |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `idle.vrma` | Idle baseline | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `idle-2.vrma` | Idle variation | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `idle-3.vrma` | Idle variation | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `idle-4.vrma` | Idle variation | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `neutral.vrma` | Neutral emote | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `happy.vrma` | Happy emote | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `sad.vrma` | Sad emote | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `angry.vrma` | Disagree emote | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `relaxed.vrma` | Neck stretch | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `relaxed-2.vrma` | Shift pivot | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `nod.vrma` | Head nod | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `shake.vrma` | Head shake | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `think.vrma` | Look around | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `raise-hand.vrma` | Hand raise | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `world-walk.vrma` | Locomotion walk | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | In-place, root translation zeroed | Allowed | Allowed |
| `world-walk-slow.vrma`| Locomotion slow | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | In-place, root translation zeroed | Allowed | Allowed |
| `world-walk-start.vrma`| Walk start transition | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Anchored to idle and walk cycle | Allowed | Allowed |
| `world-walk-stop.vrma` | Walk stop transition | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Anchored to walk cycle and idle | Allowed | Allowed |
| `world-sit-idle.vrma` | Sitting hold | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Hips height locked to 0.5409 | Allowed | Allowed |
| `world-sit-talking.vrma`| Seated conversation | Overte | High Fidelity, Inc. / Overte e.V. | Apache-2.0 | Include Overte Apache-2.0 notice | Lower body locked to sit hold | Allowed | Allowed |
| `world-sit-enter.vrma` | Stand to sit | Quaternius | Quaternius | CC0 1.0 Universal | None required (credited) | Root X/Z zeroed, edges anchored | Allowed | Allowed |
| `world-sit-exit.vrma` | Sit to stand | Quaternius | Quaternius | CC0 1.0 Universal | None required (credited) | Root X/Z zeroed, edges anchored | Allowed | Allowed |
| `rb-idle.vrma` | Expressive idle | Rocketbox | Microsoft Corporation | MIT | Include Rocketbox MIT notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `rb-happy.vrma` | Expressive happy | Rocketbox | Microsoft Corporation | MIT | Include Rocketbox MIT notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `rb-sad.vrma` | Expressive sad | Rocketbox | Microsoft Corporation | MIT | Include Rocketbox MIT notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `rb-angry.vrma` | Expressive angry | Rocketbox | Microsoft Corporation | MIT | Include Rocketbox MIT notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `rb-listen.vrma` | Active listening | Rocketbox | Microsoft Corporation | MIT | Include Rocketbox MIT notice | Retargeted to VRM 1.0, 30fps | Allowed | Allowed |
| `VRMA_01.vrma` | Full body pose | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_02.vrma` | Greeting / wave | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_03.vrma` | Peace sign | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_04.vrma` | Shoot / playful | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_05.vrma` | Spin gesture | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_06.vrma` | Model pose | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |
| `VRMA_07.vrma` | Squat / athletic | VRoid Project | pixiv Inc. | Free BOOTH Motion Pack | "Animation credits to pixiv Inc.'s VRoid Project" | Trimmed & retargeted | Allowed | Allowed with credit |

---

## 3. Full License Texts

### Apache License 2.0 (Overte)
```
Copyright (c) 2013-2019, High Fidelity, Inc.
Copyright (c) 2019-2021, Vircadia contributors.
Copyright (c) 2022-2026, Overte e.V.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### MIT License (Microsoft Rocketbox)
```
MIT License

Copyright (c) 2020 Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

### CC0 1.0 Universal (Quaternius)
```
Creative Commons Legal Code
CC0 1.0 Universal (Public Domain Dedication)
The person who associated a work with this deed has dedicated the work to the
public domain by waiving all of his or her rights to the work worldwide under
copyright law, including all related and neighboring rights, to the extent
allowed by law.
```

### pixiv Inc. VRoid Project Motion Pack
```
Animation credits to pixiv Inc.'s VRoid Project
キャラクターアニメーション: ピクシブ株式会社 VRoidプロジェクト
Usage rights granted under the official VRoid Project BOOTH Free Motion Pack Terms.
```
