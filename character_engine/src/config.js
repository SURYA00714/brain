export const CONFIG = {
  character: {
    modelPath: './models/Ao.vrm',
    scale: 1.0,
    movementSpeed: 200,       // pixels/sec walk
    runSpeed: 400,             // pixels/sec run
    jumpVelocity: 500,         // pixels/sec
    gravity: 1200,             // pixels/sec²
    arrivalDistance: 10,       // pixels
    turnLerp: 0.15,
    homePositionRatio: 0.82,   // 82% from left = bottom-right area
    homePaddingBottom: 60,
    homePaddingRight: 100,
  },
  camera: {
    fov: 30,
    near: 0.1,
    far: 20.0,
    z: 5.0,
  },
  mouse: {
    trackingEnabled: false,   // Permanently disabled: polling X11 causes pointer deadlocks
    smoothing: 0.06,
    headLimitX: 0.4,
    headLimitY: 0.5,
    followDeadZone: 80,       // pixels
    followSpeed: 150,
  },
  behavior: {
    blinkIntervalMs: 3500,
    blinkVarianceMs: 2500,
    lookAroundIntervalMs: 8000,
    lookAroundVarianceMs: 5000,
    idleActivityMinMs: 15000,     // min time before an idle activity
    idleActivityVarianceMs: 20000,
    microAnimIntervalMs: 5000,
    microAnimVarianceMs: 5000,
  },
  emotion: {
    defaultEnergy: 80,
    defaultHappiness: 60,
    defaultCuriosity: 50,
    defaultBoredom: 0,
    defaultSleepiness: 10,
    defaultPlayfulness: 40,
    energyDecayRate: 0.5,        // per minute
    boredomGrowthRate: 1.0,      // per minute of inactivity
    sleepinessGrowthRate: 0.3,   // per minute
    sleepThreshold: 80,
    boredomThreshold: 70,
    lowEnergyThreshold: 20,
  },
  dayNight: {
    nightStartHour: 22,
    nightEndHour: 7,
    nightActivityMultiplier: 0.3,  // reduce activity frequency at night
    nightSleepinessBonus: 2.0,
  },
  home: {
    props: ['sofa', 'book', 'mug', 'lamp', 'plushie'],
    restDurationMs: 10000,
    sleepDurationMs: 60000,
  },
  performance: {
    targetFPS: 30,             // Cap frame rate to 30 FPS max (prevents GPU overload)
    idleFPS: 15,               // Lower frame rate when idle/sleeping
    maxDeltaTime: 0.033,       // Max delta time clamp per frame (30 FPS equivalent)
    maxMemoryMb: 256,          // Memory threshold for watchdog check
  },
  debug: {
    enabled: false,
    logLevel: 'WARN',
  },
};
